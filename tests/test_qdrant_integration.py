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
        ingest._ensure_qdrant_collection(
            client, collection_name, ingest.QDRANT_VECTOR_DIM
        )
        points = ingest._build_qdrant_points([payload], ingest.QDRANT_VECTOR_DIM)
        client.upsert(collection_name=collection_name, points=points)
        count = client.count(collection_name=collection_name, exact=True)
        assert count.count == 1
    finally:
        client.delete_collection(collection_name=collection_name)
