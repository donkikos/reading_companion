import ingest
import db
import pytest


class _FakePoint:
    def __init__(self, payload):
        self.payload = payload
        self.id = payload.get("book_id")


class _FakeQdrantClient:
    def __init__(self, batches, collection_exists=True):
        self._batches = batches
        self._index = 0
        self._collection_exists = collection_exists
        self.deleted_collection = None

    def collection_exists(self, _collection_name):
        return self._collection_exists

    def delete_collection(self, collection_name):
        self.deleted_collection = collection_name

    def scroll(
        self,
        collection_name,
        scroll_filter=None,
        limit=256,
        offset=None,
        with_payload=True,
        with_vectors=False,
    ):
        if self._index >= len(self._batches):
            return [], None
        batch = self._batches[self._index]
        self._index += 1
        next_offset = self._index if self._index < len(self._batches) else None
        return batch, next_offset


def test_cleanup_orphaned_qdrant_chunks_removes_missing(monkeypatch):
    fake_client = _FakeQdrantClient(
        [
            [_FakePoint({"book_id": "book-1"}), _FakePoint({"book_id": "book-2"})],
            [_FakePoint({"book_id": "book-3"})],
        ]
    )
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_client)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(db, "get_all_books", lambda: [{"hash": "book-1"}])

    deleted = []

    def _delete(_client, _collection, book_id):
        deleted.append(book_id)
        return True

    monkeypatch.setattr(ingest, "_delete_qdrant_book_chunks", _delete)

    orphaned = ingest.cleanup_orphaned_qdrant_chunks(limit=2)
    assert set(orphaned) == {"book-2", "book-3"}
    assert set(deleted) == {"book-2", "book-3"}


def test_cleanup_orphaned_qdrant_chunks_skips_missing_collection(monkeypatch):
    fake_client = _FakeQdrantClient([], collection_exists=False)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_client)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(db, "get_all_books", lambda: [{"hash": "book-1"}])

    def _delete(_client, _collection, _book_id):
        raise AssertionError("delete should not be called when collection is missing")

    monkeypatch.setattr(ingest, "_delete_qdrant_book_chunks", _delete)

    orphaned = ingest.cleanup_orphaned_qdrant_chunks()
    assert orphaned == []


def test_cleanup_orphaned_qdrant_chunks_raises_when_unavailable(monkeypatch):
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: object())

    def _raise_unavailable(_client):
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.")

    monkeypatch.setattr(ingest, "_ensure_qdrant_available", _raise_unavailable)

    with pytest.raises(RuntimeError):
        ingest.cleanup_orphaned_qdrant_chunks()


def test_purge_qdrant_chunks_deletes_collection(monkeypatch):
    fake_client = _FakeQdrantClient([], collection_exists=True)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_client)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    deleted = ingest.purge_qdrant_chunks()
    assert deleted is True
    assert fake_client.deleted_collection == ingest.QDRANT_COLLECTION


def test_purge_qdrant_chunks_skips_missing_collection(monkeypatch):
    fake_client = _FakeQdrantClient([], collection_exists=False)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_client)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    deleted = ingest.purge_qdrant_chunks()
    assert deleted is False
    assert fake_client.deleted_collection is None


def test_purge_qdrant_chunks_raises_when_unavailable(monkeypatch):
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: object())

    def _raise_unavailable(_client):
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.")

    monkeypatch.setattr(ingest, "_ensure_qdrant_available", _raise_unavailable)

    with pytest.raises(RuntimeError):
        ingest.purge_qdrant_chunks()
