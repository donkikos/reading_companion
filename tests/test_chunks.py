import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ingest import Chunk, SentenceStreamItem, create_fixed_window_chunks  # noqa: E402


def _make_stream(count):
    return [
        SentenceStreamItem(seq_id=index, chapter_index=0, text=f"Sentence {index}.")
        for index in range(count)
    ]


def test_create_fixed_window_chunks_with_overlap():
    stream = _make_stream(12)

    chunks = create_fixed_window_chunks(stream)

    assert [(chunk.pos_start, chunk.pos_end) for chunk in chunks] == [(0, 7), (6, 11)]
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    for chunk in chunks:
        for offset, sentence in enumerate(chunk.sentences):
            assert sentence == stream[chunk.pos_start + offset].text
            assert chunk.pos_start + offset <= chunk.pos_end


def test_create_fixed_window_chunks_for_short_stream():
    stream = _make_stream(5)

    chunks = create_fixed_window_chunks(stream)

    assert len(chunks) == 1
    assert chunks[0].pos_start == 0
    assert chunks[0].pos_end == 4
    assert chunks[0].sentences == [item.text for item in stream]


def test_create_fixed_window_chunks_respects_chapter_boundaries():
    stream = [
        SentenceStreamItem(seq_id=0, chapter_index=0, text="C0 S0."),
        SentenceStreamItem(seq_id=1, chapter_index=0, text="C0 S1."),
        SentenceStreamItem(seq_id=2, chapter_index=0, text="C0 S2."),
        SentenceStreamItem(seq_id=3, chapter_index=1, text="C1 S0."),
        SentenceStreamItem(seq_id=4, chapter_index=1, text="C1 S1."),
    ]

    chunks = create_fixed_window_chunks(stream, window=3, overlap=1)

    assert [(chunk.pos_start, chunk.pos_end) for chunk in chunks] == [
        (0, 2),
        (2, 2),
        (3, 4),
    ]
    assert chunks[0].sentences == ["C0 S0.", "C0 S1.", "C0 S2."]
    assert chunks[1].sentences == ["C0 S2."]
    assert chunks[2].sentences == ["C1 S0.", "C1 S1."]
