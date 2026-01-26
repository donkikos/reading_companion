from types import SimpleNamespace

from fastapi.testclient import TestClient

import ingest
import main
import db


class _FakePoint:
    def __init__(self, payload, point_id):
        self.payload = payload
        self.id = point_id


class _FakeQdrantClient:
    def __init__(self, count, points):
        self._count = count
        self._points = points

    def collection_exists(self, _name):
        return True

    def count(self, **_kwargs):
        return SimpleNamespace(count=self._count)

    def scroll(self, **_kwargs):
        return self._points, None


def _setup_common(monkeypatch, tmp_path, book_id):
    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(b"fake")

    monkeypatch.setattr(db, "get_book", lambda _book_id: {"filepath": str(epub_path)})
    monkeypatch.setattr(ingest.epub, "read_epub", lambda _path: "book")
    monkeypatch.setattr(ingest, "build_sentence_stream", lambda _book: (["s1"], []))
    monkeypatch.setattr(
        ingest, "create_fixed_window_chunks", lambda _stream, **_kwargs: [1, 2, 3]
    )
    monkeypatch.setattr(ingest, "_build_qdrant_book_filter", lambda _book_id: {})


def test_verify_ingestion_ok(monkeypatch, tmp_path):
    book_id = "book123"
    _setup_common(monkeypatch, tmp_path, book_id)
    points = [
        _FakePoint(
            {
                "book_id": book_id,
                "chapter_index": 0,
                "pos_start": 0,
                "pos_end": 7,
                "sentences": ["a", "b"],
                "text": "a b",
            },
            "p1",
        ),
        _FakePoint(
            {
                "book_id": book_id,
                "chapter_index": 0,
                "pos_start": 6,
                "pos_end": 13,
                "sentences": ["c", "d"],
                "text": "c d",
            },
            "p2",
        ),
    ]
    fake_client = _FakeQdrantClient(count=3, points=points)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_client)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    client = TestClient(main.app)
    response = client.post(
        "/ingestion/verify", json={"book_id": book_id, "sample_size": 2}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["expected_chunks"] == 3
    assert payload["actual_chunks"] == 3
    assert payload["mismatches"] == []


def test_verify_ingestion_qdrant_unavailable(monkeypatch, tmp_path):
    book_id = "book123"
    _setup_common(monkeypatch, tmp_path, book_id)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: object())

    def _raise_unavailable(_client):
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.")

    monkeypatch.setattr(ingest, "_ensure_qdrant_available", _raise_unavailable)

    client = TestClient(main.app)
    response = client.post("/ingestion/verify", json={"book_id": book_id})

    assert response.status_code == 503
    assert "Qdrant is unavailable" in response.json()["detail"]


def test_verify_ingestion_reports_mismatches(monkeypatch, tmp_path):
    book_id = "book123"
    _setup_common(monkeypatch, tmp_path, book_id)
    points = [
        _FakePoint(
            {
                "book_id": book_id,
                "chapter_index": 0,
                "pos_start": 0,
                "pos_end": 7,
                "sentences": ["a"],
            },
            "p1",
        )
    ]
    fake_client = _FakeQdrantClient(count=1, points=points)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_client)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    client = TestClient(main.app)
    response = client.post(
        "/ingestion/verify", json={"book_id": book_id, "sample_size": 1}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    mismatch_types = {item["type"] for item in payload["mismatches"]}
    assert "count_mismatch" in mismatch_types
    assert "missing_fields" in mismatch_types
