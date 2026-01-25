from typing import Any

import db
import ingest
from mcp.server.fastmcp import FastMCP
from qdrant_client.http import models as qmodels

DEFAULT_LIMIT = 20
MAX_LIMIT = 256


def _normalize_limit(k: int | None, limit: int | None) -> int:
    chosen = limit if limit is not None else k
    if not isinstance(chosen, int) or chosen <= 0:
        chosen = DEFAULT_LIMIT
    return min(chosen, MAX_LIMIT)


mcp = FastMCP("Spoiler Reader")


@mcp.tool()
def list_books() -> dict[str, list[dict[str, Any]]]:
    """List all available books in the library with their IDs (hashes)."""
    books = db.get_all_books()
    return {
        "books": [
            {
                "book_id": b["hash"],
                "title": b.get("title"),
                "author": b.get("author"),
            }
            for b in books
        ]
    }


@mcp.tool()
def list_chapters(book_hash: str) -> str:
    """List chapters for a specific book."""
    chapters = db.get_chapters_list(book_hash)
    if not chapters:
        return "No chapter info available."

    report = f"Chapters for {book_hash}:\n"
    for c in chapters:
        report += f"{c['chapter_index']}: {c['title']} (Seq {c['start_seq_id']}-{c['end_seq_id']})\n"
    return report


@mcp.tool()
def get_book_context(
    book_hash: str,
    query: str = None,
    chapter_index: int = None,
    k: int = DEFAULT_LIMIT,
    limit: int | None = None,
) -> str:
    """
    Retrieve context from the book, strictly limited to what the user has read.

    Args:
        book_hash: The ID of the book.
        query: Optional semantic search query (e.g., "what did the butler say?").
        chapter_index: Optional chapter index to restrict search to.
        k: Max number of chunks/sentences to return (default 20, max 256).
        limit: Deprecated alias for k.
    """
    # 1. Get Safety Cursor
    current_cursor = db.get_reading_position(book_hash)
    if (
        current_cursor is None
        or not isinstance(current_cursor, int)
        or current_cursor < 0
    ):
        raise ValueError(
            "Reading state missing or invalid. Sync the current reading position first."
        )
    if current_cursor == 0:
        return {
            "mode": "context",
            "book_id": book_hash,
            "cursor": current_cursor,
            "status": "not_started",
            "message": "User has not started reading this book.",
        }

    # 2. Build Qdrant filter (book + cursor)
    filters = [
        qmodels.FieldCondition(
            key="book_id", match=qmodels.MatchValue(value=book_hash)
        ),
        qmodels.FieldCondition(key="pos_end", range=qmodels.Range(lte=current_cursor)),
    ]
    if chapter_index is not None:
        filters.append(
            qmodels.FieldCondition(
                key="chapter_index", match=qmodels.MatchValue(value=chapter_index)
            )
        )

    qdrant_filter = qmodels.Filter(must=filters)

    try:
        qdrant_client = ingest._get_qdrant_client()
        ingest._ensure_qdrant_available(qdrant_client)
    except RuntimeError as exc:
        return {
            "mode": "error",
            "book_id": book_hash,
            "cursor": current_cursor,
            "error": f"Qdrant unavailable: {exc}",
        }

    if not qdrant_client.collection_exists(ingest.QDRANT_COLLECTION):
        return {
            "mode": "error",
            "book_id": book_hash,
            "cursor": current_cursor,
            "error": f"Qdrant collection '{ingest.QDRANT_COLLECTION}' is missing.",
        }

    limit = _normalize_limit(k, limit)

    def _merge_search_chunks(points):
        chunks = []
        for point in points:
            payload = point.payload or {}
            pos_start = payload.get("pos_start")
            sentences = payload.get("sentences") or []
            text = payload.get("text")
            chapter = payload.get("chapter_index", "?")
            if not isinstance(pos_start, int):
                continue
            if not sentences and isinstance(text, str) and text:
                sentences = [text]
            if not sentences:
                continue
            pos_end = payload.get("pos_end")
            if not isinstance(pos_end, int):
                pos_end = pos_start + len(sentences) - 1
            chunks.append(
                {
                    "chapter": chapter,
                    "pos_start": pos_start,
                    "pos_end": pos_end,
                    "sentences": sentences,
                }
            )

        if not chunks:
            return []

        chunks.sort(key=lambda item: (item["chapter"], item["pos_start"]))
        merged = []
        current = None
        current_sentences_by_seq = {}
        current_order = []

        def _flush_current():
            if not current:
                return
            ordered = [current_sentences_by_seq[seq] for seq in current_order]
            merged.append(
                {
                    "chapter": current["chapter"],
                    "pos_start": current["pos_start"],
                    "pos_end": current["pos_end"],
                    "text": " ".join(ordered),
                }
            )

        for chunk in chunks:
            if (
                current
                and chunk["chapter"] == current["chapter"]
                and chunk["pos_start"] <= current["pos_end"] + 1
            ):
                start = chunk["pos_start"]
                for idx, sentence in enumerate(chunk["sentences"]):
                    seq_id = start + idx
                    if seq_id in current_sentences_by_seq:
                        continue
                    current_sentences_by_seq[seq_id] = sentence
                    current_order.append(seq_id)
                current["pos_end"] = max(current["pos_end"], chunk["pos_end"])
                continue

            _flush_current()
            current = {
                "chapter": chunk["chapter"],
                "pos_start": chunk["pos_start"],
                "pos_end": chunk["pos_end"],
            }
            current_sentences_by_seq = {}
            current_order = []
            for idx, sentence in enumerate(chunk["sentences"]):
                seq_id = chunk["pos_start"] + idx
                current_sentences_by_seq[seq_id] = sentence
                current_order.append(seq_id)

        _flush_current()
        return merged

    if query:
        try:
            query_vector = ingest._tei_embed(query)[0]
        except RuntimeError as exc:
            return {
                "mode": "error",
                "book_id": book_hash,
                "cursor": current_cursor,
                "error": f"Embedding unavailable: {exc}",
            }

        if hasattr(qdrant_client, "query_points"):
            query_response = qdrant_client.query_points(
                collection_name=ingest.QDRANT_COLLECTION,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            results = query_response.points
        else:
            results = qdrant_client.search(
                collection_name=ingest.QDRANT_COLLECTION,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

        if not results:
            return {
                "mode": "search",
                "book_id": book_hash,
                "cursor": current_cursor,
                "query": query,
                "chunks": [],
                "message": "No matching context found within current reading progress.",
            }

        merged_chunks = _merge_search_chunks(results)
        return {
            "mode": "search",
            "book_id": book_hash,
            "cursor": current_cursor,
            "query": query,
            "chunks": merged_chunks,
        }

    # Context Retrieval (Recent history or Chapter specific)
    # TODO: Optimize context retrieval to avoid wide scroll + dedupe; consider a
    # sentence-level index or ordered range queries to fetch the last N sentences.
    max_total = max(limit * 10, 200)
    collected = []
    offset = None
    while len(collected) < max_total:
        points, offset = qdrant_client.scroll(
            collection_name=ingest.QDRANT_COLLECTION,
            scroll_filter=qdrant_filter,
            limit=min(256, max_total - len(collected)),
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break
        collected.extend(points)
        if offset is None:
            break

    if not collected:
        return {
            "mode": "context",
            "book_id": book_hash,
            "cursor": current_cursor,
            "sentences": [],
            "message": "No context found.",
        }

    sentences_by_seq = {}
    for point in collected:
        payload = point.payload or {}
        pos_start = payload.get("pos_start")
        sentences = payload.get("sentences") or []
        if not isinstance(pos_start, int):
            continue
        for idx, sentence in enumerate(sentences):
            seq_id = pos_start + idx
            if seq_id > current_cursor:
                break
            if seq_id not in sentences_by_seq:
                sentences_by_seq[seq_id] = sentence

    if not sentences_by_seq:
        return {
            "mode": "context",
            "book_id": book_hash,
            "cursor": current_cursor,
            "sentences": [],
            "message": "No context found.",
        }

    sorted_items = sorted(sentences_by_seq.items(), key=lambda item: item[0])
    selected = [{"seq_id": seq_id, "text": sentence} for seq_id, sentence in sorted_items][
        -limit:
    ]

    return {
        "mode": "context",
        "book_id": book_hash,
        "cursor": current_cursor,
        "sentences": selected,
    }


if __name__ == "__main__":
    mcp.run()
