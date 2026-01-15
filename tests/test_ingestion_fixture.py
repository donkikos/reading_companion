from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import db
import ingest
import main


class _FakeCollection:
    def __init__(self):
        self._documents = []

    def add(self, ids, documents, metadatas):
        self._documents.extend(zip(ids, documents, metadatas))

    def delete(self, **_kwargs):
        self._documents = []


class _FakeChromaClient:
    def __init__(self):
        self._collection = _FakeCollection()

    def get_or_create_collection(self, name):
        return self._collection


class _FakeQdrantClient:
    def __init__(self, vector_dim):
        self._vector_dim = vector_dim
        self._collection_exists = True
        self._points = []

    def get_collections(self):
        return []

    def collection_exists(self, _name):
        return self._collection_exists

    def get_collection(self, _name):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=self._vector_dim))
            )
        )

    def create_collection(self, **_kwargs):
        self._collection_exists = True

    def upsert(self, collection_name, points):
        self._points = list(points)

    def count(self, **_kwargs):
        return SimpleNamespace(count=len(self._points))

    def scroll(self, **_kwargs):
        limit = _kwargs.get("limit")
        points = self._points if limit is None else self._points[:limit]
        return points, None


def test_ingest_fixture_and_verify_qdrant(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    monkeypatch.setattr(ingest, "chroma_client", _FakeChromaClient())

    fake_qdrant = _FakeQdrantClient(ingest.QDRANT_VECTOR_DIM)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    fixture_path = Path(__file__).parent / "fixtures" / "minimal.epub"
    book_id = ingest.ingest_epub(str(fixture_path))

    epub_book = ingest.epub.read_epub(str(fixture_path))
    stream, _chapters = ingest.build_sentence_stream(epub_book)
    expected_chunks = len(ingest.create_fixed_window_chunks(stream))

    client = TestClient(main.app)
    response = client.post(
        "/ingestion/verify",
        json={"book_id": book_id, "sample_size": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["expected_chunks"] == expected_chunks
    assert payload["actual_chunks"] == expected_chunks
