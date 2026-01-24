import spacy
import hashlib
import ebooklib
import json
import logging
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from ebooklib import epub
from bs4 import BeautifulSoup
import db

# Initialize Spacy
_NLP = None
logger = logging.getLogger(__name__)
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "book_chunks")
_RAW_QDRANT_VECTOR_DIM = os.getenv("QDRANT_VECTOR_DIM")
QDRANT_VECTOR_DIM = int(_RAW_QDRANT_VECTOR_DIM) if _RAW_QDRANT_VECTOR_DIM else None
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_PATH = os.getenv("QDRANT_PATH")
TEI_BASE_URL = os.getenv("TEI_BASE_URL", "http://localhost:8080")
TEI_MODEL = os.getenv("TEI_MODEL", "BAAI/bge-base-en-v1.5")
_RAW_TEI_BATCH_SIZE = os.getenv("TEI_BATCH_SIZE")
TEI_BATCH_SIZE = int(_RAW_TEI_BATCH_SIZE) if _RAW_TEI_BATCH_SIZE else 8
_RAW_TEI_TIMEOUT = os.getenv("TEI_TIMEOUT")
TEI_TIMEOUT = float(_RAW_TEI_TIMEOUT) if _RAW_TEI_TIMEOUT else 30.0

INGESTION_STAGES = (
    ("hashing", "Hashing...", 5),
    ("parsing", "Parsing...", 35),
    ("chunking", "Chunking...", 10),
    ("embedding", "Embedding...", 20),
    ("qdrant", "Qdrant upsert...", 20),
    ("metadata", "Metadata save...", 10),
)


def _build_stage_ranges():
    ranges = {}
    start = 0
    for key, label, weight in INGESTION_STAGES:
        end = start + weight
        ranges[key] = (start, end, label)
        start = end
    if start != 100:
        raise ValueError("INGESTION_STAGES must sum to 100")
    return ranges


INGESTION_STAGE_RANGES = _build_stage_ranges()
INGESTION_STAGE_INDEX = {
    key: index + 1 for index, (key, _label, _weight) in enumerate(INGESTION_STAGES)
}
INGESTION_STAGE_TOTAL = len(INGESTION_STAGES)


def _get_metrics_logger():
    metrics_logger = logging.getLogger("ingest.metrics")
    if not metrics_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        metrics_logger.addHandler(handler)
    else:
        for handler in metrics_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.stream = sys.stdout
    metrics_logger.setLevel(logging.DEBUG)
    metrics_logger.propagate = False
    return metrics_logger


class IngestionProgress:
    def __init__(self, callback):
        self._callback = callback

    def stage(self, stage_key, stage_percent, message=None, detail=None):
        if not self._callback:
            return

        _start, _end, default_label = INGESTION_STAGE_RANGES[stage_key]
        stage_percent = max(0, min(100, stage_percent))
        stage_index = INGESTION_STAGE_INDEX[stage_key]
        label = message or default_label
        self._callback(
            f"({stage_index}/{INGESTION_STAGE_TOTAL}) {label}",
            stage_percent,
            detail,
        )


def get_file_hash(filepath):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def clean_html(html_content):
    """Extract text from HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    # Add space after block elements to prevent merging words
    for block in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "br"]):
        block.append(" ")
    return soup.get_text()


def get_nlp():
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:
            _NLP = spacy.blank("en")
            if "sentencizer" not in _NLP.pipe_names:
                _NLP.add_pipe("sentencizer")
    return _NLP


def extract_sentences(text):
    """Split text into sentences using Spacy."""
    doc = get_nlp()(text)
    # Filter out very short or empty sentences
    return [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 5]


@dataclass(frozen=True)
class SentenceStreamItem:
    seq_id: int
    chapter_index: int
    text: str


@dataclass(frozen=True)
class Chunk:
    pos_start: int
    pos_end: int
    sentences: list[str]


def extract_chapter_title(raw_content, chapter_index):
    chapter_title = f"Chapter {chapter_index + 1}"
    soup = BeautifulSoup(raw_content, "html.parser")
    h1 = soup.find("h1")
    if h1:
        chapter_title = h1.get_text().strip()
    return chapter_title


def is_spine_document(item):
    if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
        return False
    if item.get_id() == "nav" or item.get_name() == "nav.xhtml":
        return False
    return True


def build_sentence_stream(book, progress_callback=None):
    """Return ordered sentence stream and chapter ranges for deterministic indexing."""
    stream = []
    chapters = []
    seq_id = 0
    chapter_index = 0

    chapter_sentences = []
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)

        if not is_spine_document(item):
            continue

        raw_content = item.get_content()
        text = clean_html(raw_content)
        sentences = extract_sentences(text)

        if not sentences:
            continue

        chapter_title = extract_chapter_title(raw_content, chapter_index)
        chapter_sentences.append((chapter_index, chapter_title, sentences))
        chapter_index += 1

    total_sentences = sum(len(sentences) for _, _, sentences in chapter_sentences)
    processed_sentences = 0

    for chapter_index, chapter_title, sentences in chapter_sentences:
        start_seq = seq_id

        for sentence in sentences:
            stream.append(SentenceStreamItem(seq_id, chapter_index, sentence))
            seq_id += 1
            processed_sentences += 1

            if progress_callback and total_sentences > 0:
                percent = int((processed_sentences / total_sentences) * 100)
                progress_callback(f"Processing {chapter_title}", percent)

        end_seq = seq_id - 1
        chapters.append((chapter_index, chapter_title, start_seq, end_seq))

    return stream, chapters


def _chapter_ranges_from_stream(stream):
    """Return chapter_index ranges as (chapter_index, start_idx, end_idx)."""
    if not stream:
        return []

    ranges = []
    current_chapter = stream[0].chapter_index
    start_idx = 0

    for idx, item in enumerate(stream[1:], start=1):
        if item.chapter_index != current_chapter:
            ranges.append((current_chapter, start_idx, idx - 1))
            current_chapter = item.chapter_index
            start_idx = idx

    ranges.append((current_chapter, start_idx, len(stream) - 1))
    return ranges


def create_fixed_window_chunks(stream, chapters=None, window=8, overlap=2):
    """Create fixed-window sentence chunks with overlap, per chapter."""
    if overlap < 0 or overlap >= window:
        raise ValueError("overlap must be >= 0 and less than window")

    if not stream:
        return []

    if chapters is None:
        chapter_ranges = _chapter_ranges_from_stream(stream)
    else:
        chapter_ranges = []
        for entry in chapters:
            if len(entry) == 4:
                chapter_index, _title, start_seq, end_seq = entry
            elif len(entry) == 3:
                chapter_index, start_seq, end_seq = entry
            else:
                raise ValueError(
                    "chapters entries must be (index, start, end) or include title"
                )
            chapter_ranges.append((chapter_index, start_seq, end_seq))

    step = window - overlap
    chunks = []

    for _chapter_index, start_idx, end_idx in chapter_ranges:
        start = start_idx
        while start <= end_idx:
            end = min(start + window, end_idx + 1)
            sentences = [item.text for item in stream[start:end]]
            chunks.append(Chunk(start, end - 1, sentences))
            start += step

    return chunks


def build_chunk_payloads(book_id, stream, chunks):
    """Build Qdrant payloads for each chunk."""
    if not chunks:
        return []

    payloads = []
    for chunk in chunks:
        start_item = stream[chunk.pos_start]
        end_item = stream[chunk.pos_end]
        payloads.append(
            {
                "book_id": book_id,
                "chapter_index": start_item.chapter_index,
                "pos_start": start_item.seq_id,
                "pos_end": end_item.seq_id,
                "sentences": list(chunk.sentences),
                "text": " ".join(chunk.sentences),
            }
        )
    return payloads


def _hash_embedding(text, dim):
    """Deterministic fallback embedding derived from full text."""
    if dim <= 0:
        raise ValueError("Embedding dimension must be positive")
    if not text:
        return [0.0] * dim

    values = []
    counter = 0
    while len(values) < dim:
        digest = hashlib.blake2b(
            f"{counter}:{text}".encode("utf-8"), digest_size=32
        ).digest()
        for offset in range(0, len(digest), 4):
            if len(values) >= dim:
                break
            chunk = digest[offset : offset + 4]
            value = int.from_bytes(chunk, "little", signed=False)
            values.append((value / 2**32) * 2 - 1)
        counter += 1
    return values


def _tei_embed(texts, base_url=None, batch_size=None, progress_callback=None):
    if base_url is None:
        base_url = TEI_BASE_URL
    if isinstance(texts, str):
        texts = [texts]

    if not texts:
        return []

    if batch_size is None:
        batch_size = TEI_BATCH_SIZE
    if batch_size is not None and batch_size <= 0:
        raise ValueError("TEI_BATCH_SIZE must be a positive integer.")

    url = f"{base_url.rstrip('/')}/embed"
    embeddings = []
    step = batch_size or len(texts)
    total = len(texts)
    total_batches = (total + step - 1) // step
    processed = 0
    for batch_index, offset in enumerate(range(0, len(texts), step), start=1):
        batch = texts[offset : offset + step]
        payload = {"inputs": batch if len(batch) > 1 else batch[0]}
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(request, timeout=TEI_TIMEOUT) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8") if exc.fp else ""
            raise RuntimeError(
                f"TEI embedding request failed ({exc.code}): {message}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "TEI embedding service is unavailable; ingestion cannot proceed."
            ) from exc

        result = json.loads(body)
        if not isinstance(result, list):
            raise RuntimeError("TEI embedding response is not a list.")

        if result and isinstance(result[0], (int, float)):
            batch_embeddings = [result]
        else:
            batch_embeddings = result

        if len(batch_embeddings) != len(batch):
            raise RuntimeError("TEI embedding response length mismatch.")

        embeddings.extend(batch_embeddings)
        processed += len(batch)
        if progress_callback:
            progress_callback(processed, total, batch_index, total_batches)

    return embeddings


def _get_qdrant_client():
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("qdrant-client is required for Qdrant ingestion") from exc

    if QDRANT_PATH:
        return QdrantClient(path=QDRANT_PATH)
    if QDRANT_URL:
        return QdrantClient(url=QDRANT_URL)
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def _ensure_qdrant_collection(client, collection_name, vector_dim):
    from qdrant_client.http import models as qmodels

    if client.collection_exists(collection_name):
        info = client.get_collection(collection_name)
        existing_size = info.config.params.vectors.size
        if existing_size != vector_dim:
            raise ValueError(
                f"Qdrant collection '{collection_name}' vector size "
                f"{existing_size} does not match required {vector_dim}"
            )
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(
            size=vector_dim, distance=qmodels.Distance.COSINE
        ),
    )


def _ensure_qdrant_available(client):
    try:
        client.get_collections()
    except Exception as exc:
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.") from exc


def _build_qdrant_book_filter(book_id):
    from qdrant_client.http import models as qmodels

    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="book_id", match=qmodels.MatchValue(value=book_id)
            )
        ]
    )


def _delete_qdrant_book_chunks(client, collection_name, book_id):
    from qdrant_client.http import models as qmodels

    if not client.collection_exists(collection_name):
        return False

    selector = qmodels.FilterSelector(filter=_build_qdrant_book_filter(book_id))
    client.delete(collection_name=collection_name, points_selector=selector)
    return True


def purge_qdrant_chunks():
    qdrant_client = _get_qdrant_client()
    try:
        _ensure_qdrant_available(qdrant_client)
    except RuntimeError as exc:
        logger.error("Qdrant purge failed: %s", exc)
        raise

    collection_name = QDRANT_COLLECTION
    if not qdrant_client.collection_exists(collection_name):
        logger.info("Qdrant purge skipped; collection '%s' missing.", collection_name)
        return False

    qdrant_client.delete_collection(collection_name)
    logger.info("Qdrant purge deleted collection '%s'.", collection_name)
    return True


def cleanup_orphaned_qdrant_chunks(limit=256):
    qdrant_client = _get_qdrant_client()
    try:
        _ensure_qdrant_available(qdrant_client)
    except RuntimeError as exc:
        logger.error("Startup Qdrant cleanup failed: %s", exc)
        raise

    collection_name = QDRANT_COLLECTION
    if not qdrant_client.collection_exists(collection_name):
        logger.info(
            "Startup Qdrant cleanup skipped; collection '%s' missing.", collection_name
        )
        return []

    known_books = {book["hash"] for book in db.get_all_books()}
    orphaned = set()
    offset = None
    while True:
        points, offset = qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=None,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            book_id = payload.get("book_id")
            if not book_id:
                continue
            if book_id not in known_books:
                orphaned.add(book_id)
        if offset is None:
            break

    if not orphaned:
        logger.info("Startup Qdrant cleanup found no orphaned book ids.")
        return []

    for book_id in sorted(orphaned):
        _delete_qdrant_book_chunks(qdrant_client, collection_name, book_id)

    logger.info("Startup Qdrant cleanup removed %d orphaned book ids.", len(orphaned))
    return sorted(orphaned)


def _build_qdrant_points(payloads, vector_dim, progress_callback=None):
    from qdrant_client.http import models as qmodels

    if not payloads:
        return [], vector_dim

    texts = [payload["text"] for payload in payloads]
    embeddings = _tei_embed(texts, progress_callback=progress_callback)
    if not embeddings:
        raise RuntimeError("TEI embeddings are empty.")

    resolved_dim = len(embeddings[0])
    for vector in embeddings:
        if len(vector) != resolved_dim:
            raise ValueError("TEI returned inconsistent embedding dimensions.")

    if vector_dim is not None and resolved_dim != vector_dim:
        raise ValueError(
            f"TEI embedding dimension {resolved_dim} does not match "
            f"Qdrant vector size {vector_dim}"
        )

    points = []
    for payload, vector in zip(payloads, embeddings):
        # Use deterministic UUIDs to satisfy Qdrant's point ID requirements.
        point_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"{payload['book_id']}:{payload['pos_start']}"
        )
        points.append(qmodels.PointStruct(id=point_id, vector=vector, payload=payload))
    return points, resolved_dim


def ingest_epub(epub_path, progress_callback=None):
    """Parse EPUB, tokenize sentences, and store in Qdrant & SQLite."""
    print(f"Ingesting: {epub_path}")
    ingest_start = time.monotonic()
    embedding_seconds = 0.0
    qdrant_seconds = 0.0
    chunks_processed = 0
    progress = IngestionProgress(progress_callback)

    # 1. Hashing and Deduplication
    progress.stage("hashing", 0)
    book_hash = get_file_hash(epub_path)
    progress.stage("hashing", 100)

    existing = db.get_book(book_hash)
    is_reingest = existing is not None
    if is_reingest:
        print(f"Re-ingesting existing book: {existing['title']} ({book_hash})")

    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"Error reading EPUB: {e}")
        raise e

    # Metadata
    title = (
        book.get_metadata("DC", "title")[0][0]
        if book.get_metadata("DC", "title")
        else "Unknown Title"
    )
    author = (
        book.get_metadata("DC", "creator")[0][0]
        if book.get_metadata("DC", "creator")
        else "Unknown Author"
    )

    print(f"Processing '{title}' by {author}")

    chapters_data = []  # For SQL

    if is_reingest:
        db.delete_chapters(book_hash)

    progress.stage("parsing", 0)

    def parsing_progress(message, percent):
        progress.stage("parsing", percent, detail=f"{percent}%")

    stream, chapters = build_sentence_stream(book, parsing_progress)
    progress.stage("parsing", 100)

    progress.stage("chunking", 0)
    chunks = create_fixed_window_chunks(stream, chapters=chapters)
    progress.stage("chunking", 100)
    chunk_payloads = build_chunk_payloads(book_hash, stream, chunks)
    chunks_processed = len(chunk_payloads)
    embedding_model = TEI_MODEL
    embedding_dim = None

    if chunk_payloads:
        qdrant_client = _get_qdrant_client()
        _ensure_qdrant_available(qdrant_client)
        progress.stage("embedding", 0)
        embedding_start = time.monotonic()
        def embedding_progress(processed, total, batch_index, total_batches):
            if total <= 0:
                return
            percent = int((processed / total) * 100)
            progress.stage(
                "embedding",
                percent,
                detail=f"{percent}%",
            )

        points, vector_dim = _build_qdrant_points(
            chunk_payloads,
            QDRANT_VECTOR_DIM,
            progress_callback=embedding_progress,
        )
        embedding_seconds = time.monotonic() - embedding_start
        embedding_dim = vector_dim
        progress.stage("embedding", 100)
        _ensure_qdrant_collection(qdrant_client, QDRANT_COLLECTION, vector_dim)
        if is_reingest:
            _delete_qdrant_book_chunks(qdrant_client, QDRANT_COLLECTION, book_hash)
        progress.stage("qdrant", 0)
        qdrant_start = time.monotonic()
        qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        qdrant_seconds = time.monotonic() - qdrant_start
        progress.stage("qdrant", 100)

    progress.stage("metadata", 0)
    for chapter_index, chapter_title, start_seq, end_seq in chapters:
        chapters_data.append(
            (book_hash, chapter_index, chapter_title, start_seq, end_seq)
        )

    # 2. Store in SQLite
    if is_reingest:
        db.update_book_metadata(
            book_hash,
            title,
            author,
            epub_path,
            len(stream),
            embedding_model,
            embedding_dim,
        )
    else:
        db.add_book(
            book_hash,
            title,
            author,
            epub_path,
            len(stream),
            embedding_model,
            embedding_dim,
        )
    db.add_chapters(chapters_data)

    # Initialize reading state
    if not is_reingest:
        db.update_cursor(book_hash, 0)

    progress.stage("metadata", 100)

    total_seconds = time.monotonic() - ingest_start
    chunks_per_second = (chunks_processed / total_seconds) if total_seconds else 0.0
    metrics = {
        "event": "ingestion_metrics",
        "book_id": book_hash,
        "total_time_s": round(total_seconds, 3),
        "embedding_time_s": round(embedding_seconds, 3),
        "qdrant_upsert_time_s": round(qdrant_seconds, 3),
        "chunks_processed": chunks_processed,
        "chunks_per_sec": round(chunks_per_second, 3),
    }
    _get_metrics_logger().debug(json.dumps(metrics))

    print(f"Finished ingesting. ID: {book_hash}. Total sequences: {len(stream)}")
    return book_hash


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        ingest_epub(sys.argv[1])
    else:
        print("Usage: python ingest.py <path_to_epub>")
