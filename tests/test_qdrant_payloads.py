import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ingest import (  # noqa: E402
    SentenceStreamItem,
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
    assert first["pos_end"] == 2
    assert first["sentences"] == [
        "First sentence.",
        "Second sentence.",
        "Third sentence.",
    ]
    assert first["text"] == "First sentence. Second sentence. Third sentence."

    second = payloads[1]
    assert second["chapter_index"] == 1
    assert second["pos_start"] == 2
    assert second["pos_end"] == 3
