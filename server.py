from typing import Any

import db
import ingest
from mcp.server.fastmcp import FastMCP
from qdrant_client.http import models as qmodels

DEFAULT_LIMIT = 20

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
    book_hash: str, query: str = None, chapter_index: int = None, limit: int = 20
) -> str:
    """
    Retrieve context from the book, strictly limited to what the user has read.

    Args:
        book_hash: The ID of the book.
        query: Optional semantic search query (e.g., "what did the butler say?").
        chapter_index: Optional chapter index to restrict search to.
        limit: Max number of sentences to return (default 20).
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
        return "User has not started reading this book."

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
        return f"Qdrant unavailable: {exc}"

    if not qdrant_client.collection_exists(ingest.QDRANT_COLLECTION):
        return f"Qdrant collection '{ingest.QDRANT_COLLECTION}' is missing."

    limit = limit or DEFAULT_LIMIT

    if query:
        try:
            query_vector = ingest._tei_embed(query)[0]
        except RuntimeError as exc:
            return f"Embedding unavailable: {exc}"

        results = qdrant_client.search(
            collection_name=ingest.QDRANT_COLLECTION,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            return "No matching context found within current reading progress."

        response = f"--- Search Results (User read up to {current_cursor}) ---\n"
        for point in results:
            payload = point.payload or {}
            seq = payload.get("pos_start", 0)
            chap = payload.get("chapter_index", "?")
            text = payload.get("text", "")
            response += f"[Ch{chap}:Seq{seq}] {text}\n"
        return response

    # Context Retrieval (Recent history or Chapter specific)
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
        return "No context found."

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
        return "No context found."

    sorted_items = sorted(sentences_by_seq.items(), key=lambda item: item[0])
    selected = [sentence for _, sentence in sorted_items][-limit:]

    response = f"--- Context (User read up to {current_cursor}) ---\n"
    for sentence in selected:
        response += f"{sentence}\n"

    return response


if __name__ == "__main__":
    mcp.run()
