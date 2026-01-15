import os
import re
import shutil
import uuid
import ingest
import db
import chromadb
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path=".data/chroma_db")
collection = chroma_client.get_or_create_collection(name="library")

# Ensure books directory
BOOKS_DIR = os.path.abspath(".data/books")
os.makedirs(BOOKS_DIR, exist_ok=True)

# In-memory task store (Use Redis/DB for production)
tasks: Dict[str, Dict] = {}


class SyncRequest(BaseModel):
    book_hash: str
    text: str
    cfi: str = None  # Added CFI


class VerifyIngestionRequest(BaseModel):
    book_id: str
    sample_size: int = 5


def run_ingestion_task(task_id: str, file_path: str):
    tasks[task_id]["status"] = "processing"
    tasks[task_id]["progress"] = 0

    def update_progress(msg, percent):
        tasks[task_id]["message"] = msg
        tasks[task_id]["progress"] = percent

    try:
        book_hash = ingest.ingest_epub(file_path, progress_callback=update_progress)

        # Rename file to hash
        final_path = os.path.join(BOOKS_DIR, f"{book_hash}.epub")
        if not os.path.exists(final_path):
            os.rename(file_path, final_path)
            db.update_book_path(book_hash, final_path)
        else:
            # Cleanup temp if duplicate
            if os.path.exists(file_path):
                os.remove(file_path)

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["book_hash"] = book_hash
        tasks[task_id]["progress"] = 100

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/books")
def list_books():
    return db.get_all_books()


@app.get("/books/{book_hash}")
def get_book_details(book_hash: str):
    details = db.get_book_details(book_hash)
    if not details:
        raise HTTPException(status_code=404, detail="Book not found")
    return details


@app.post("/upload")
async def upload_book(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    temp_path = os.path.join(BOOKS_DIR, f"temp_{task_id}.epub")

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    tasks[task_id] = {"status": "pending", "progress": 0, "message": "Queued"}

    background_tasks.add_task(run_ingestion_task, task_id, temp_path)

    return {"task_id": task_id}


@app.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


def normalize_text(text):
    """Aggressively normalize text: lower, strip non-alphanum, single spaces."""
    # Remove all non-alphanumeric chars (keep spaces)
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    # Collapse whitespace
    return " ".join(text.split())


@app.post("/sync")
async def sync_position(request: SyncRequest):
    print(f"\n--- SYNC REQUEST ---\nClient Text: '{request.text}'")
    if request.cfi:
        print(f"Client CFI: {request.cfi}")

    # Query ChromaDB for the closest match WITHIN this book
    results = collection.query(
        query_texts=[request.text], n_results=1, where={"book_hash": request.book_hash}
    )

    if not results["documents"][0]:
        print("Result: No semantic match found in vector DB.")
        return JSONResponse(content={"status": "no_match"}, status_code=404)

    distance = results["distances"][0][0]
    matched_text = results["documents"][0][0]
    metadata = results["metadatas"][0][0]

    print(f"Top Semantic Candidate: '{matched_text}' (Distance: {distance:.4f})")

    # Improved Matching Logic
    is_match = distance < 0.4

    if not is_match:
        # Fallback: Aggressive Normalization
        req_norm = normalize_text(request.text)
        match_norm = normalize_text(matched_text)

        # Check substrings
        if req_norm in match_norm or match_norm in req_norm:
            print("Fallback: Substring match confirmed after normalization.")
            is_match = True
        else:
            print(f"Fallback Failed.\nReq Norm: {req_norm}\nMatch Norm: {match_norm}")

    if is_match:
        seq_id = metadata["seq_id"]
        db.update_cursor(request.book_hash, seq_id, cfi=request.cfi)

        # Fetch updated details to return chapter info
        details = db.get_book_details(request.book_hash)

        return {
            "status": "synced",
            "seq_id": seq_id,
            "chapter_title": details["chapter_title"],
            "distance": distance,
        }
    else:
        return JSONResponse(
            content={"status": "poor_match", "distance": distance}, status_code=400
        )


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


@app.post("/ingestion/verify")
def verify_ingestion(request: VerifyIngestionRequest):
    book = db.get_book(request.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    epub_path = book.get("filepath")
    if not epub_path or not os.path.exists(epub_path):
        raise HTTPException(status_code=404, detail="Book file not found")

    try:
        epub_book = ingest.epub.read_epub(epub_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read EPUB: {exc}"
        ) from exc

    stream, _chapters = ingest.build_sentence_stream(epub_book)
    expected_chunks = len(ingest.create_fixed_window_chunks(stream))

    try:
        qdrant_client = ingest._get_qdrant_client()
        ingest._ensure_qdrant_available(qdrant_client)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    mismatches = []
    collection_name = ingest.QDRANT_COLLECTION
    if not qdrant_client.collection_exists(collection_name):
        mismatches.append({"type": "collection_missing", "collection": collection_name})
        return {
            "ok": False,
            "book_id": request.book_id,
            "expected_chunks": expected_chunks,
            "actual_chunks": 0,
            "sample_size": 0,
            "mismatches": mismatches,
        }

    book_filter = ingest._build_qdrant_book_filter(request.book_id)
    count_result = qdrant_client.count(
        collection_name=collection_name, count_filter=book_filter, exact=True
    )
    actual_chunks = count_result.count
    if actual_chunks != expected_chunks:
        mismatches.append(
            {
                "type": "count_mismatch",
                "expected": expected_chunks,
                "actual": actual_chunks,
            }
        )

    sample_size = request.sample_size
    if sample_size < 0:
        mismatches.append({"type": "invalid_sample_size", "value": sample_size})
        sample_size = 0
    sample_size = min(sample_size, actual_chunks)

    required_fields = {
        "book_id",
        "chapter_index",
        "pos_start",
        "pos_end",
        "sentences",
        "text",
    }
    monotonic_candidates = []

    if sample_size:
        points, _ = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=book_filter,
            limit=sample_size,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}
            missing = sorted(required_fields - payload.keys())
            if missing:
                mismatches.append(
                    {
                        "type": "missing_fields",
                        "point_id": point.id,
                        "missing": missing,
                    }
                )
                continue

            if payload["book_id"] != request.book_id:
                mismatches.append(
                    {
                        "type": "book_id_mismatch",
                        "point_id": point.id,
                        "value": payload["book_id"],
                    }
                )

            if not _is_int(payload["chapter_index"]):
                mismatches.append(
                    {
                        "type": "invalid_chapter_index",
                        "point_id": point.id,
                        "value": payload["chapter_index"],
                    }
                )

            if not _is_int(payload["pos_start"]) or not _is_int(payload["pos_end"]):
                mismatches.append(
                    {
                        "type": "invalid_positions",
                        "point_id": point.id,
                        "pos_start": payload["pos_start"],
                        "pos_end": payload["pos_end"],
                    }
                )
            else:
                if payload["pos_start"] > payload["pos_end"]:
                    mismatches.append(
                        {
                            "type": "position_order",
                            "point_id": point.id,
                            "pos_start": payload["pos_start"],
                            "pos_end": payload["pos_end"],
                        }
                    )
                else:
                    monotonic_candidates.append(
                        (payload["pos_start"], payload["pos_end"], point.id)
                    )

            if not isinstance(payload["sentences"], list):
                mismatches.append(
                    {
                        "type": "invalid_sentences",
                        "point_id": point.id,
                        "value": payload["sentences"],
                    }
                )

            if not isinstance(payload["text"], str):
                mismatches.append(
                    {
                        "type": "invalid_text",
                        "point_id": point.id,
                        "value": payload["text"],
                    }
                )

        monotonic_candidates.sort(key=lambda item: item[0])
        prev_start = None
        prev_end = None
        for start, end, point_id in monotonic_candidates:
            if prev_start is not None and start <= prev_start:
                mismatches.append(
                    {
                        "type": "non_monotonic_pos_start",
                        "point_id": point_id,
                        "pos_start": start,
                        "prev_pos_start": prev_start,
                    }
                )
            if prev_end is not None and end <= prev_end:
                mismatches.append(
                    {
                        "type": "non_monotonic_pos_end",
                        "point_id": point_id,
                        "pos_end": end,
                        "prev_pos_end": prev_end,
                    }
                )
            prev_start = start
            prev_end = end

    ok = len(mismatches) == 0
    return {
        "ok": ok,
        "book_id": request.book_id,
        "expected_chunks": expected_chunks,
        "actual_chunks": actual_chunks,
        "sample_size": sample_size,
        "mismatches": mismatches,
    }


app.mount("/files", StaticFiles(directory=BOOKS_DIR), name="files")
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
