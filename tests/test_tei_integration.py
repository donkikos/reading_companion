import os
import uuid

import pytest

import db
import ingest


def _qdrant_available(client):
    try:
        client.get_collections()
    except Exception:
        return False
    return True


def test_end_to_end_ingestion_with_tei_embeddings(monkeypatch):
    client = ingest._get_qdrant_client()
    if not _qdrant_available(client):
        pytest.skip("Qdrant not available")

    try:
        ingest._tei_embed(["ping"])
    except RuntimeError as exc:
        pytest.skip(f"TEI unavailable: {exc}")

    collection_name = f"test_tei_ingest_{uuid.uuid4().hex}"
    monkeypatch.setattr(ingest, "QDRANT_COLLECTION", collection_name)
    monkeypatch.setattr(ingest, "TEI_MODEL", os.getenv("TEI_MODEL", ingest.TEI_MODEL))

    epub_path = os.path.join("tests", "fixtures", "minimal.epub")
    book_hash = ingest.get_file_hash(epub_path)
    collection = ingest.chroma_client.get_or_create_collection(name="library")
    collection.delete(where={"book_hash": book_hash})
    db.delete_book_data(book_hash)

    try:
        ingested_id = ingest.ingest_epub(epub_path)
        assert ingested_id == book_hash

        scroll_filter = ingest._build_qdrant_book_filter(book_hash)
        count = client.count(
            collection_name=collection_name, count_filter=scroll_filter, exact=True
        )
        assert count.count > 0

        points, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=1,
            with_vectors=True,
        )
        assert points
        vector = points[0].vector
        assert vector is not None
        assert len(vector) > 0
    finally:
        collection.delete(where={"book_hash": book_hash})
        db.delete_book_data(book_hash)
        if client.collection_exists(collection_name):
            client.delete_collection(collection_name)
