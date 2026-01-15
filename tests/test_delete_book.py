from pathlib import Path
from fastapi.testclient import TestClient

import db
import ingest
import main


class _FakeCollection:
    def __init__(self):
        self.deleted = False
        self.where = None

    def delete(self, **kwargs):
        self.deleted = True
        self.where = kwargs.get("where")


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

    fake_collection = _FakeCollection()
    monkeypatch.setattr(main, "collection", fake_collection)

    fake_qdrant = _FakeQdrantClient()
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    client = TestClient(main.app)
    response = client.delete(f"/books/{book_hash}")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fake_collection.deleted is True
    assert fake_collection.where == {"book_hash": book_hash}
    assert fake_qdrant.deleted is True
    assert db.get_book(book_hash) is None
    assert db.get_chapters_list(book_hash) == []
    assert db.get_cursor(book_hash) == 0
    assert not Path(str(epub_path)).exists()
