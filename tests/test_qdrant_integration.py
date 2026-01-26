import uuid

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

import db
import ingest
import server


def _qdrant_available(client):
    try:
        client.get_collections()
    except Exception:
        return False
    return True


def test_qdrant_upsert_accepts_point_ids():
    client = QdrantClient(
        host=ingest.QDRANT_HOST,
        port=ingest.QDRANT_PORT,
    )
    if not _qdrant_available(client):
        pytest.skip("Qdrant not available")

    collection_name = f"test_point_ids_{uuid.uuid4().hex}"
    payload = {
        "book_id": "book123",
        "chapter_index": 0,
        "pos_start": 0,
        "pos_end": 0,
        "sentences": ["Hello"],
        "text": "Hello",
    }

    try:
        vector_dim = ingest.QDRANT_VECTOR_DIM or 8
        ingest._ensure_qdrant_collection(client, collection_name, vector_dim)

        def fake_embed(texts, **_kwargs):
            return [ingest._hash_embedding(text, dim=vector_dim) for text in texts]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(ingest, "_tei_embed", fake_embed)
            points, resolved_dim = ingest._build_qdrant_points([payload], vector_dim)
        assert resolved_dim == vector_dim
        client.upsert(collection_name=collection_name, points=points)
        count = client.count(collection_name=collection_name, exact=True)
        assert count.count == 1
    finally:
        client.delete_collection(collection_name=collection_name)


def test_get_book_context_uses_query_points(monkeypatch, tmp_path):
    client = QdrantClient(
        host=ingest.QDRANT_HOST,
        port=ingest.QDRANT_PORT,
    )
    if not _qdrant_available(client):
        pytest.skip("Qdrant not available")

    collection_name = f"test_query_points_{uuid.uuid4().hex}"
    book_hash = "book123"
    vector_dim = 8
    payload = {
        "book_id": book_hash,
        "chapter_index": 0,
        "pos_start": 0,
        "pos_end": 3,
        "sentences": ["Yatima was a citizen."],
        "text": "Yatima was a citizen.",
    }
    vector = ingest._hash_embedding(payload["text"], dim=vector_dim)

    try:
        ingest._ensure_qdrant_collection(client, collection_name, vector_dim)
        point = qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=payload,
        )
        client.upsert(collection_name=collection_name, points=[point])

        db_path = tmp_path / "state.db"
        monkeypatch.setattr(db, "DB_PATH", str(db_path))
        db.init_db()
        db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)
        db.update_cursor(book_hash, 5)

        monkeypatch.setattr(ingest, "QDRANT_COLLECTION", collection_name)
        monkeypatch.setattr(ingest, "_tei_embed", lambda _text: [vector])

        response = server.get_book_context(book_hash, query="Who is Yatima?", k=5)

        assert payload["text"] in response["chunks"][0]["text"]
    finally:
        db.delete_book_data(book_hash)
        if client.collection_exists(collection_name):
            client.delete_collection(collection_name=collection_name)
