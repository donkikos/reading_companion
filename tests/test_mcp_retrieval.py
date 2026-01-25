import db
import ingest
import server


class _FakeQdrantClient:
    def __init__(self, points=None):
        self.last_filter = None
        self.last_limit = None
        self._points = points or []

    def collection_exists(self, _name):
        return True

    def query_points(self, **kwargs):
        self.last_filter = kwargs.get("query_filter")
        self.last_limit = kwargs.get("limit")
        return _FakeQueryResponse(self._points)


class _FakeQueryResponse:
    def __init__(self, points):
        self.points = points


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
    assert response["status"] == "not_started"
    assert response["message"] == "User has not started reading this book."


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
    assert response["chunks"] == []
    assert "No matching context found" in response["message"]

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

    response = server.get_book_context(book_hash, k=10)

    texts = [item["text"] for item in response["sentences"]]
    assert "Sentence 2" in texts
    assert "Sentence 3" in texts
    assert "Sentence 4" in texts
    assert "Sentence 5" not in texts


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

    response = server.get_book_context(book_hash, k=10)

    texts = [item["text"] for item in response["sentences"]]
    assert texts == [
        "Sentence 0",
        "Sentence 1",
        "Sentence 2",
        "Sentence 3",
        "Sentence 4",
    ]


def test_get_book_context_caps_k_at_max(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)
    db.update_cursor(book_hash, 5)

    fake_qdrant = _FakeQdrantClient()
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(ingest, "_tei_embed", lambda _text: [[0.1, 0.2]])

    server.get_book_context(book_hash, query="test", k=300)

    assert fake_qdrant.last_limit == server.MAX_LIMIT


def test_get_book_context_merges_overlapping_query_chunks(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path)
    book_hash = "book123"
    db.add_book(book_hash, "Title", "Author", "/tmp/book.epub", 10)
    db.update_cursor(book_hash, 10)

    points = [
        _FakePoint(
            {
                "book_id": book_hash,
                "chapter_index": 4,
                "pos_start": 794,
                "pos_end": 796,
                "sentences": [
                    "Hashim's piece was a distillation of the idea of friendship,",
                    "within and across all borders.",
                    "And whether it was all down to the outlook or not,",
                ],
                "text": "A",
            }
        ),
        _FakePoint(
            {
                "book_id": book_hash,
                "chapter_index": 4,
                "pos_start": 795,
                "pos_end": 797,
                "sentences": [
                    "within and across all borders.",
                    "And whether it was all down to the outlook or not,",
                    "Yatima was glad to be witnessing it.",
                ],
                "text": "B",
            }
        ),
    ]
    fake_qdrant = _FakeQdrantClient(points)
    monkeypatch.setattr(ingest, "_get_qdrant_client", lambda: fake_qdrant)
    monkeypatch.setattr(ingest, "_ensure_qdrant_available", lambda _client: None)
    monkeypatch.setattr(ingest, "_tei_embed", lambda _text: [[0.1, 0.2]])

    response = server.get_book_context(book_hash, query="test", k=10)

    assert response["chunks"][0]["pos_start"] == 794
    assert response["chunks"][0]["pos_end"] == 797
    text = response["chunks"][0]["text"]
    assert text.count("Hashim's piece was a distillation of the idea of friendship,") == 1
