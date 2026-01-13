import sys
from pathlib import Path

from ebooklib import epub

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ingest import build_sentence_stream  # noqa: E402


def _write_sample_book(tmp_path):
    book = epub.EpubBook()
    book.set_identifier("sample-book")
    book.set_title("Sample Book")
    book.set_language("en")

    chapter_one = epub.EpubHtml(
        title="Chapter 1",
        file_name="chap_1.xhtml",
        content="<h1>Chapter 1</h1><p>First sentence. Second sentence.</p>",
    )
    chapter_two = epub.EpubHtml(
        title="Chapter 2",
        file_name="chap_2.xhtml",
        content="<h1>Chapter 2</h1><p>Third sentence.</p>",
    )

    book.add_item(chapter_one)
    book.add_item(chapter_two)
    book.toc = (chapter_one, chapter_two)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter_one, chapter_two]

    book_path = tmp_path / "sample.epub"
    epub.write_epub(str(book_path), book)
    return book_path


def test_build_sentence_stream_is_ordered_and_contiguous(tmp_path):
    book_path = _write_sample_book(tmp_path)
    book = epub.read_epub(str(book_path))

    stream, chapters = build_sentence_stream(book)

    assert [item.seq_id for item in stream] == list(range(len(stream)))
    normalized = [" ".join(item.text.split()) for item in stream]
    assert normalized == [
        "Chapter 1 First sentence.",
        "Second sentence.",
        "Chapter 2 Third sentence.",
    ]
    assert [item.chapter_index for item in stream] == [0, 0, 1]
    assert chapters == [
        (0, "Chapter 1", 0, 1),
        (1, "Chapter 2", 2, 2),
    ]


def test_build_sentence_stream_reports_progress(tmp_path):
    book_path = _write_sample_book(tmp_path)
    book = epub.read_epub(str(book_path))

    updates = []

    def record_progress(message, percent):
        updates.append((message, percent))

    build_sentence_stream(book, progress_callback=record_progress)

    assert [percent for _, percent in updates] == [33, 66, 100]
    assert [message for message, _ in updates] == [
        "Processing Chapter 1",
        "Processing Chapter 1",
        "Processing Chapter 2",
    ]
