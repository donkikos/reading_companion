import uuid

import pytest
from qdrant_client import QdrantClient

import ingest


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
            mp.setattr(ingest, "_ollama_embed", fake_embed)
            points, resolved_dim = ingest._build_qdrant_points([payload], vector_dim)
        assert resolved_dim == vector_dim
        client.upsert(collection_name=collection_name, points=points)
        count = client.count(collection_name=collection_name, exact=True)
        assert count.count == 1
    finally:
        client.delete_collection(collection_name=collection_name)
