import os
import db
import chromadb
from mcp.server.fastmcp import FastMCP

# Initialize ChromaDB
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, ".data", "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="library")

mcp = FastMCP("Spoiler Reader")


@mcp.tool()
def list_books() -> str:
    """List all available books in the library with their IDs (hashes)."""
    books = db.get_all_books()
    if not books:
        return "No books in library."

    report = "Available Books:\n"
    for b in books:
        report += f"- {b['title']} by {b['author']} (ID: {b['hash']})\n"
    return report


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
    current_cursor = db.get_cursor(book_hash)
    if current_cursor == 0:
        return "User has not started reading this book."

    # 2. Build Filter
    # Base filter: book_hash AND seq_id <= current_cursor
    filters = [{"book_hash": {"$eq": book_hash}}, {"seq_id": {"$lte": current_cursor}}]

    # Chapter restriction
    if chapter_index is not None:
        filters.append({"chapter_index": {"$eq": chapter_index}})

    final_filter = {"$and": filters}

    # 3. Execute Query
    results = None

    if query:
        # Semantic Search
        print(f"DEBUG: Querying '{query}' with filter {final_filter}")
        results = collection.query(
            query_texts=[query], n_results=limit, where=final_filter
        )
        # Flatten results (Chroma returns list of lists)
        docs = results["documents"][0]
        metas = results["metadatas"][0]

        if not docs:
            return "No matching context found within current reading progress."

        # For semantic search, we might want to return them ranked by relevance (already done by query)
        # OR sorted by sequence order to make a coherent story?
        # Usually RAG prefers relevance. But let's sort by sequence for readability if they are close?
        # Let's stick to relevance but include location info.

        response = f"--- Search Results (User read up to {current_cursor}) ---\n"
        for i, doc in enumerate(docs):
            seq = metas[i]["seq_id"]
            chap = metas[i]["chapter_index"]
            response += f"[Ch{chap}:Seq{seq}] {doc}\n"
        return response

    else:
        # Context Retrieval (Recent history or Chapter specific)
        # If no query, we just want the *last* read sentences, or the chapter text.

        # We use .get() but we want to sort. Chroma .get() supports limit/offset but not sort direction efficiently in API.
        # We fetch a chunk.

        print(f"DEBUG: Fetching context with filter {final_filter}")
        results = collection.get(
            where=final_filter,
            limit=limit * 2,  # Fetch more to allow Python-side sorting/filtering
            include=["documents", "metadatas"],
        )

        if not results["documents"]:
            return "No context found."

        # Zip and Sort by seq_id
        zipped = zip(results["metadatas"], results["documents"])
        # Sort ascending
        sorted_docs = sorted(zipped, key=lambda x: x[0]["seq_id"])

        # If we just want "context", usually we mean "what just happened?" -> Last items.
        # If chapter_index was specified, we might want the *start* of the chapter?
        # Let's assume "recent context" (tail) is default behavior if no query.

        selected_docs = sorted_docs[-limit:]

        response = f"--- Context (User read up to {current_cursor}) ---\n"
        for meta, doc in selected_docs:
            response += f"{doc}\n"

        return response


if __name__ == "__main__":
    mcp.run()
