from pathlib import Path
from fastapi.testclient import TestClient

import db
import ingest
import main


class _FakeQdrantClient:
    def __init__(self):
        self.deleted = False

    def collection_exists(self, _name):
        return True

    def delete(self, **_kwargs):
        self.deleted = True


def test_delete_book_removes_data(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(b"fake")

    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", str(epub_path), 10)
    db.add_chapters([(book_hash, 0, "Chapter 1", 0, 9)])
    db.update_cursor(book_hash, 5)

    fake_qdrant = _FakeQdrantClient()
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    client = TestClient(main.app)
    response = client.delete(f"/books/{book_hash}")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fake_qdrant.deleted is True
    assert db.get_book(book_hash) is None
    assert db.get_chapters_list(book_hash) == []
    assert db.get_cursor(book_hash) == 0
    assert not Path(str(epub_path)).exists()


def test_reingest_updates_path_when_final_exists(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    book_hash = "book123"
    temp_path = tmp_path / "temp.epub"
    temp_path.write_bytes(b"temp")
    final_path = tmp_path / f"{book_hash}.epub"
    final_path.write_bytes(b"existing")

    db.add_book(book_hash, "Title", "Author", str(temp_path), 10)
    monkeypatch.setattr(ingest, "ingest_epub", lambda *_args, **_kwargs: book_hash)

    main.BOOKS_DIR = str(tmp_path)
    main.tasks["task-1"] = {}
    main.run_ingestion_task("task-1", str(temp_path))

    assert db.get_book(book_hash)["filepath"] == str(final_path)
    assert not temp_path.exists()


def test_delete_book_missing_returns_404(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    fake_qdrant = _FakeQdrantClient()
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    client = TestClient(main.app)
    response = client.delete("/books/missing-book")

    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found"
    assert fake_qdrant.deleted is False


def test_delete_book_qdrant_unavailable(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(b"fake")
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", str(epub_path), 10)

    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: object())

    def _raise_unavailable(_client):
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.")

    monkeypatch.setattr(ingest, "_ensure_qdrant_available", _raise_unavailable)

    client = TestClient(main.app)
    response = client.delete(f"/books/{book_hash}")

    assert response.status_code == 503
    assert "Qdrant is unavailable" in response.json()["detail"]
