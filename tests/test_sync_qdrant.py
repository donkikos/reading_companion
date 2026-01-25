from types import SimpleNamespace

from fastapi.testclient import TestClient

import db
import ingest
import main


class _FakeQdrantClient:
    def __init__(self, payloads):
        self._payloads = payloads

    def get_collections(self):
        return []

    def collection_exists(self, _name):
        return True

    def query_points(self, **_kwargs):
        points = [
            SimpleNamespace(payload=payload, score=0.9) for payload in self._payloads
        ]
        return _FakeQueryResponse(points)


class _FakeQueryResponse:
    def __init__(self, points):
        self.points = points


def test_sync_updates_cursor_from_qdrant_payload(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 50)
    db.add_chapters([(book_hash, 0, "Chapter 1", 0, 49)])

    payload = {
        "book_id": book_hash,
        "chapter_index": 0,
        "pos_start": 10,
        "pos_end": 17,
        "sentences": ["The quick brown fox", "jumps over the lazy dog"],
        "text": "The quick brown fox jumps over the lazy dog",
    }

    fake_qdrant = _FakeQdrantClient([payload])
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(ingest, "_tei_embed", lambda _text, **_kwargs: [[0.1, 0.2]])

    client = TestClient(main.app)
    response = client.post(
        "/sync",
        json={
            "book_hash": book_hash,
            "text": "brown fox",
            "cfi": "epubcfi(/6/2[chap01]!/4/1:0)",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "synced"
    assert payload["seq_id"] == 10
    assert db.get_cursor(book_hash) == 10


def test_sync_returns_no_match_when_empty(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 50)
    db.add_chapters([(book_hash, 0, "Chapter 1", 0, 49)])

    fake_qdrant = _FakeQdrantClient([])
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(ingest, "_tei_embed", lambda _text, **_kwargs: [[0.1, 0.2]])

    client = TestClient(main.app)
    response = client.post(
        "/sync",
        json={
            "book_hash": book_hash,
            "text": "brown fox",
            "cfi": "epubcfi(/6/2[chap01]!/4/1:0)",
        },
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "no_match"


def test_sync_qdrant_unavailable(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: object())

    def _raise_unavailable(_client):
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.")

    monkeypatch.setattr(ingest, "_ensure_qdrant_available", _raise_unavailable)

    client = TestClient(main.app)
    response = client.post(
        "/sync",
        json={
            "book_hash": "book123",
            "text": "brown fox",
            "cfi": "epubcfi(/6/2[chap01]!/4/1:0)",
        },
    )

    assert response.status_code == 503
    assert "Qdrant is unavailable" in response.json()["detail"]


def test_sync_tei_unavailable(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    fake_qdrant = _FakeQdrantClient([])
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    def _raise_unavailable(_text, **_kwargs):
        raise RuntimeError("TEI embedding service is unavailable.")

    monkeypatch.setattr(ingest, "_tei_embed", _raise_unavailable)

    client = TestClient(main.app)
    response = client.post(
        "/sync",
        json={
            "book_hash": "book123",
            "text": "brown fox",
            "cfi": "epubcfi(/6/2[chap01]!/4/1:0)",
        },
    )

    assert response.status_code == 503
    assert "TEI embedding service is unavailable" in response.json()["detail"]


def test_sync_rejects_empty_query(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    fake_qdrant = _FakeQdrantClient([])
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    client = TestClient(main.app)
    response = client.post(
        "/sync",
        json={
            "book_hash": "book123",
            "text": "   ",
            "cfi": "epubcfi(/6/2[chap01]!/4/1:0)",
        },
    )

    assert response.status_code == 400
    assert "Query text must not be empty" in response.json()["detail"]
