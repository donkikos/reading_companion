import spacy
import chromadb
import hashlib
import ebooklib
from dataclasses import dataclass
from ebooklib import epub
from bs4 import BeautifulSoup
import db

# Initialize Spacy and ChromaDB
_NLP = None
chroma_client = chromadb.PersistentClient(path=".data/chroma_db")


def get_file_hash(filepath):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def clean_html(html_content):
    """Extract text from HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    # Add space after block elements to prevent merging words
    for block in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "br"]):
        block.append(" ")
    return soup.get_text()


def get_nlp():
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:
            _NLP = spacy.blank("en")
            if "sentencizer" not in _NLP.pipe_names:
                _NLP.add_pipe("sentencizer")
    return _NLP


def extract_sentences(text):
    """Split text into sentences using Spacy."""
    doc = get_nlp()(text)
    # Filter out very short or empty sentences
    return [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 5]


@dataclass(frozen=True)
class SentenceStreamItem:
    seq_id: int
    chapter_index: int
    text: str


def extract_chapter_title(raw_content, chapter_index):
    chapter_title = f"Chapter {chapter_index + 1}"
    soup = BeautifulSoup(raw_content, "html.parser")
    h1 = soup.find("h1")
    if h1:
        chapter_title = h1.get_text().strip()
    return chapter_title


def is_spine_document(item):
    if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
        return False
    if item.get_id() == "nav" or item.get_name() == "nav.xhtml":
        return False
    return True


def build_sentence_stream(book, progress_callback=None):
    """Return ordered sentence stream and chapter ranges for deterministic indexing."""
    stream = []
    chapters = []
    seq_id = 0
    chapter_index = 0

    spine_items = [
        item for item in book.spine if is_spine_document(book.get_item_with_id(item[0]))
    ]
    total_items = len(spine_items)
    processed_items = 0

    for item_id, linear in book.spine:
        item = book.get_item_with_id(item_id)

        if not is_spine_document(item):
            continue

        raw_content = item.get_content()
        text = clean_html(raw_content)
        sentences = extract_sentences(text)
        processed_items += 1

        if not sentences:
            if progress_callback and total_items > 0:
                percent = int((processed_items / total_items) * 100)
                progress_callback("Processing", percent)
            continue

        chapter_title = extract_chapter_title(raw_content, chapter_index)
        start_seq = seq_id

        for sentence in sentences:
            stream.append(SentenceStreamItem(seq_id, chapter_index, sentence))
            seq_id += 1

        end_seq = seq_id - 1
        chapters.append((chapter_index, chapter_title, start_seq, end_seq))

        if progress_callback and total_items > 0:
            percent = int((processed_items / total_items) * 100)
            progress_callback(f"Processing {chapter_title}", percent)

        chapter_index += 1

    return stream, chapters


def ingest_epub(epub_path, progress_callback=None):
    """Parse EPUB, tokenize sentences, and store in ChromaDB & SQLite."""
    print(f"Ingesting: {epub_path}")

    # 1. Hashing and Deduplication
    if progress_callback:
        progress_callback("Hashing...", 0)
    book_hash = get_file_hash(epub_path)

    existing = db.get_book(book_hash)
    if existing:
        print(f"Book already exists: {existing['title']} ({book_hash})")
        if progress_callback:
            progress_callback("Done", 100)
        return book_hash

    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"Error reading EPUB: {e}")
        raise e

    # Metadata
    title = (
        book.get_metadata("DC", "title")[0][0]
        if book.get_metadata("DC", "title")
        else "Unknown Title"
    )
    author = (
        book.get_metadata("DC", "creator")[0][0]
        if book.get_metadata("DC", "creator")
        else "Unknown Author"
    )

    print(f"Processing '{title}' by {author}")

    # Chroma Collection
    collection = chroma_client.get_or_create_collection(name="library")

    chapters_data = []  # For SQL

    # Batch storage
    ids = []
    documents = []
    metadatas = []

    stream, chapters = build_sentence_stream(book, progress_callback)

    for item in stream:
        ids.append(f"{book_hash}_{item.seq_id}")
        documents.append(item.text)
        metadatas.append(
            {
                "book_hash": book_hash,
                "seq_id": item.seq_id,
                "chapter_index": item.chapter_index,
            }
        )

        if len(ids) >= 500:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            ids = []
            documents = []
            metadatas = []

    for chapter_index, chapter_title, start_seq, end_seq in chapters:
        chapters_data.append(
            (book_hash, chapter_index, chapter_title, start_seq, end_seq)
        )

    # Flush remaining
    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)

    # 2. Store in SQLite
    db.add_book(book_hash, title, author, epub_path, len(stream))
    db.add_chapters(chapters_data)

    # Initialize reading state
    db.update_cursor(book_hash, 0)

    if progress_callback:
        progress_callback("Completed", 100)

    print(f"Finished ingesting. ID: {book_hash}. Total sequences: {len(stream)}")
    return book_hash


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        ingest_epub(sys.argv[1])
    else:
        print("Usage: python ingest.py <path_to_epub>")
