import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from ingest import (  # noqa: E402
    SentenceStreamItem,
    _build_qdrant_book_filter,
    _delete_qdrant_book_chunks,
    _ensure_qdrant_available,
    build_chunk_payloads,
    create_fixed_window_chunks,
)


def test_build_chunk_payloads_includes_expected_fields():
    stream = [
        SentenceStreamItem(seq_id=0, chapter_index=0, text="First sentence."),
        SentenceStreamItem(seq_id=1, chapter_index=0, text="Second sentence."),
        SentenceStreamItem(seq_id=2, chapter_index=1, text="Third sentence."),
        SentenceStreamItem(seq_id=3, chapter_index=1, text="Fourth sentence."),
    ]
    chunks = create_fixed_window_chunks(stream, window=3, overlap=1)

    payloads = build_chunk_payloads("book-123", stream, chunks)

    assert len(payloads) == 2
    first = payloads[0]
    assert first["book_id"] == "book-123"
    assert first["chapter_index"] == 0
    assert first["pos_start"] == 0
    assert first["pos_end"] == 1
    assert first["sentences"] == [
        "First sentence.",
        "Second sentence.",
    ]
    assert first["text"] == "First sentence. Second sentence."

    second = payloads[1]
    assert second["chapter_index"] == 1
    assert second["pos_start"] == 2
    assert second["pos_end"] == 3


def test_build_qdrant_book_filter_targets_book_id():
    filt = _build_qdrant_book_filter("book-xyz")

    assert filt.must[0].key == "book_id"
    assert filt.must[0].match.value == "book-xyz"


def test_delete_qdrant_book_chunks_skips_when_collection_missing():
    class FakeClient:
        def __init__(self):
            self.deleted = False

        def collection_exists(self, _):
            return False

        def delete(self, **_):
            self.deleted = True

    client = FakeClient()
    deleted = _delete_qdrant_book_chunks(client, "missing", "book-xyz")

    assert deleted is False
    assert client.deleted is False


def test_ensure_qdrant_available_raises_when_unreachable():
    class FakeClient:
        def get_collections(self):
            raise ConnectionError("offline")

    with pytest.raises(RuntimeError, match="Qdrant is unavailable"):
        _ensure_qdrant_available(FakeClient())


def test_ensure_qdrant_available_noop_when_reachable():
    class FakeClient:
        def get_collections(self):
            return {"collections": []}

    _ensure_qdrant_available(FakeClient())
