import json
import os
import uuid
import urllib.request

import pytest

import db
import ingest


def _qdrant_available(client):
    try:
        client.get_collections()
    except Exception:
        return False
    return True


def _ollama_models(base_url):
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8")
    except Exception:
        return []
    payload = json.loads(body)
    return [
        model.get("name") for model in payload.get("models", []) if model.get("name")
    ]


def _resolve_ollama_model(base_url):
    models = _ollama_models(base_url)
    if not models:
        return None
    configured = os.getenv("OLLAMA_MODEL")
    if configured and configured in models:
        return configured
    return models[0]


def test_end_to_end_ingestion_with_ollama_embeddings(monkeypatch):
    client = ingest._get_qdrant_client()
    if not _qdrant_available(client):
        pytest.skip("Qdrant not available")

    model = _resolve_ollama_model(ingest.OLLAMA_BASE_URL)
    if not model:
        pytest.skip("No Ollama models available")

    try:
        ingest._ollama_embed(["ping"], model=model)
    except RuntimeError as exc:
        pytest.skip(f"Ollama unavailable: {exc}")

    collection_name = f"test_ollama_ingest_{uuid.uuid4().hex}"
    monkeypatch.setattr(ingest, "QDRANT_COLLECTION", collection_name)
    monkeypatch.setattr(ingest, "OLLAMA_MODEL", model)

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
