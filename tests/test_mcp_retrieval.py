import db
import ingest
import server


class _FakeQdrantClient:
    def __init__(self):
        self.last_filter = None

    def collection_exists(self, _name):
        return True

    def search(self, **kwargs):
        self.last_filter = kwargs.get("query_filter")
        return []


class _FakePoint:
    def __init__(self, payload):
        self.payload = payload


class _FakeScrollQdrantClient:
    def __init__(self, points):
        self._points = points

    def collection_exists(self, _name):
        return True

    def scroll(self, **_kwargs):
        return self._points, None


def _setup_db(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()


def test_list_books_returns_schema(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)

    payload = server.list_books()

    assert isinstance(payload, dict)
    assert payload["books"] == [
        {"book_id": book_hash, "title": "Title", "author": "Author"}
    ]


def test_get_book_context_requires_reading_state(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    db.add_book("book123", "Title", "Author", "/tmp/book.epub", 10)

    def _boom():
        raise AssertionError("Qdrant should not be touched without reading state")

    monkeypatch.setattr(ingest, "_get_qdrant_client", _boom)

    try:
        server.get_book_context("book123")
    except ValueError as exc:
        assert "Reading state missing or invalid" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing reading state")


def test_get_book_context_zero_position(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)
    db.update_cursor(book_hash, 0)

    def _boom():
        raise AssertionError("Qdrant should not be touched when user_pos is 0")

    monkeypatch.setattr(ingest, "_get_qdrant_client", _boom)

    response = server.get_book_context(book_hash)
    assert response == "User has not started reading this book."


def test_get_book_context_filters_by_book_and_position(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)
    db.update_cursor(book_hash, 5)

    fake_qdrant = _FakeQdrantClient()
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(ingest, "_tei_embed", lambda _text: [[0.1, 0.2]])

    response = server.get_book_context(book_hash, query="test")
    assert response == "No matching context found within current reading progress."

    qdrant_filter = fake_qdrant.last_filter
    assert qdrant_filter is not None
    must_filters = qdrant_filter.must or []
    book_match = next(f for f in must_filters if getattr(f, "key", None) == "book_id")
    pos_match = next(f for f in must_filters if getattr(f, "key", None) == "pos_end")
    assert book_match.match.value == book_hash
    assert pos_match.range.lte == 5


def test_get_book_context_truncates_sentences_at_cursor(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)
    db.update_cursor(book_hash, 4)

    points = [
        _FakePoint(
            {
                "book_id": book_hash,
                "chapter_index": 0,
                "pos_start": 2,
                "pos_end": 10,
                "sentences": [
                    "Sentence 2",
                    "Sentence 3",
                    "Sentence 4",
                    "Sentence 5",
                ],
            }
        )
    ]
    fake_qdrant = _FakeScrollQdrantClient(points)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    response = server.get_book_context(book_hash, limit=10)

    assert "Sentence 2" in response
    assert "Sentence 3" in response
    assert "Sentence 4" in response
    assert "Sentence 5" not in response


def test_get_book_context_dedupes_overlapping_sentences(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)
    db.update_cursor(book_hash, 10)

    points = [
        _FakePoint(
            {
                "book_id": book_hash,
                "chapter_index": 0,
                "pos_start": 0,
                "pos_end": 4,
                "sentences": [
                    "Sentence 0",
                    "Sentence 1",
                    "Sentence 2",
                    "Sentence 3",
                ],
            }
        ),
        _FakePoint(
            {
                "book_id": book_hash,
                "chapter_index": 0,
                "pos_start": 2,
                "pos_end": 6,
                "sentences": [
                    "Sentence 2",
                    "Sentence 3",
                    "Sentence 4",
                ],
            }
        ),
    ]
    fake_qdrant = _FakeScrollQdrantClient(points)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)

    response = server.get_book_context(book_hash, limit=10)

    lines = [
        line for line in response.splitlines() if line and not line.startswith("---")
    ]
    assert lines == [
        "Sentence 0",
        "Sentence 1",
        "Sentence 2",
        "Sentence 3",
        "Sentence 4",
    ]
