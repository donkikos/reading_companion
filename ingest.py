import spacy
import chromadb
import hashlib
import ebooklib
import os
from dataclasses import dataclass
from ebooklib import epub
from bs4 import BeautifulSoup
import db

# Initialize Spacy and ChromaDB
_NLP = None
chroma_client = chromadb.PersistentClient(path=".data/chroma_db")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "book_chunks")
QDRANT_VECTOR_DIM = int(os.getenv("QDRANT_VECTOR_DIM", "128"))
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_PATH = os.getenv("QDRANT_PATH")


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


@dataclass(frozen=True)
class Chunk:
    pos_start: int
    pos_end: int
    sentences: list[str]


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

    chapter_sentences = []
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)

        if not is_spine_document(item):
            continue

        raw_content = item.get_content()
        text = clean_html(raw_content)
        sentences = extract_sentences(text)

        if not sentences:
            continue

        chapter_title = extract_chapter_title(raw_content, chapter_index)
        chapter_sentences.append((chapter_index, chapter_title, sentences))
        chapter_index += 1

    total_sentences = sum(len(sentences) for _, _, sentences in chapter_sentences)
    processed_sentences = 0

    for chapter_index, chapter_title, sentences in chapter_sentences:
        start_seq = seq_id

        for sentence in sentences:
            stream.append(SentenceStreamItem(seq_id, chapter_index, sentence))
            seq_id += 1
            processed_sentences += 1

            if progress_callback and total_sentences > 0:
                percent = int((processed_sentences / total_sentences) * 100)
                progress_callback(f"Processing {chapter_title}", percent)

        end_seq = seq_id - 1
        chapters.append((chapter_index, chapter_title, start_seq, end_seq))

    return stream, chapters


def create_fixed_window_chunks(stream, window=8, overlap=2):
    """Create fixed-window sentence chunks with overlap."""
    if overlap < 0 or overlap >= window:
        raise ValueError("overlap must be >= 0 and less than window")

    if not stream:
        return []

    step = window - overlap
    chunks = []
    start = 0

    while start < len(stream):
        end = min(start + window, len(stream))
        sentences = [item.text for item in stream[start:end]]
        chunks.append(Chunk(start, end - 1, sentences))
        start += step

    return chunks


def build_chunk_payloads(book_id, stream, chunks):
    """Build Qdrant payloads for each chunk."""
    if not chunks:
        return []

    payloads = []
    for chunk in chunks:
        start_item = stream[chunk.pos_start]
        end_item = stream[chunk.pos_end]
        payloads.append(
            {
                "book_id": book_id,
                "chapter_index": start_item.chapter_index,
                "pos_start": start_item.seq_id,
                "pos_end": end_item.seq_id,
                "sentences": list(chunk.sentences),
                "text": " ".join(chunk.sentences),
            }
        )
    return payloads


def _hash_embedding(text, dim=QDRANT_VECTOR_DIM):
    """Deterministic fallback embedding derived from full text."""
    if dim <= 0:
        raise ValueError("Embedding dimension must be positive")
    if not text:
        return [0.0] * dim

    values = []
    counter = 0
    while len(values) < dim:
        digest = hashlib.blake2b(
            f"{counter}:{text}".encode("utf-8"), digest_size=32
        ).digest()
        for offset in range(0, len(digest), 4):
            if len(values) >= dim:
                break
            chunk = digest[offset : offset + 4]
            value = int.from_bytes(chunk, "little", signed=False)
            values.append((value / 2**32) * 2 - 1)
        counter += 1
    return values


def _get_qdrant_client():
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("qdrant-client is required for Qdrant ingestion") from exc

    if QDRANT_PATH:
        return QdrantClient(path=QDRANT_PATH)
    if QDRANT_URL:
        return QdrantClient(url=QDRANT_URL)
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def _ensure_qdrant_collection(client, collection_name, vector_dim):
    from qdrant_client.http import models as qmodels

    if client.collection_exists(collection_name):
        info = client.get_collection(collection_name)
        existing_size = info.config.params.vectors.size
        if existing_size != vector_dim:
            raise ValueError(
                f"Qdrant collection '{collection_name}' vector size "
                f"{existing_size} does not match required {vector_dim}"
            )
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(
            size=vector_dim, distance=qmodels.Distance.COSINE
        ),
    )


def _ensure_qdrant_available(client):
    try:
        client.get_collections()
    except Exception as exc:
        raise RuntimeError("Qdrant is unavailable; ingestion cannot proceed.") from exc


def _build_qdrant_book_filter(book_id):
    from qdrant_client.http import models as qmodels

    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="book_id", match=qmodels.MatchValue(value=book_id)
            )
        ]
    )


def _delete_qdrant_book_chunks(client, collection_name, book_id):
    from qdrant_client.http import models as qmodels

    if not client.collection_exists(collection_name):
        return False

    selector = qmodels.FilterSelector(filter=_build_qdrant_book_filter(book_id))
    client.delete(collection_name=collection_name, points_selector=selector)
    return True


def _build_qdrant_points(payloads, vector_dim):
    from qdrant_client.http import models as qmodels

    points = []
    for payload in payloads:
        point_id = f"{payload['book_id']}:{payload['pos_start']}"
        vector = _hash_embedding(payload["text"], dim=vector_dim)
        points.append(qmodels.PointStruct(id=point_id, vector=vector, payload=payload))
    return points


def ingest_epub(epub_path, progress_callback=None):
    """Parse EPUB, tokenize sentences, and store in ChromaDB & SQLite."""
    print(f"Ingesting: {epub_path}")

    # 1. Hashing and Deduplication
    if progress_callback:
        progress_callback("Hashing...", 0)
    book_hash = get_file_hash(epub_path)

    existing = db.get_book(book_hash)
    is_reingest = existing is not None
    if is_reingest:
        print(f"Re-ingesting existing book: {existing['title']} ({book_hash})")
        if progress_callback:
            progress_callback("Re-indexing...", 0)

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

    if is_reingest:
        collection.delete(where={"book_hash": book_hash})
        db.delete_chapters(book_hash)

    stream, chapters = build_sentence_stream(book, progress_callback)

    chunks = create_fixed_window_chunks(stream)
    chunk_payloads = build_chunk_payloads(book_hash, stream, chunks)

    if chunk_payloads:
        qdrant_client = _get_qdrant_client()
        _ensure_qdrant_available(qdrant_client)
        _ensure_qdrant_collection(qdrant_client, QDRANT_COLLECTION, QDRANT_VECTOR_DIM)
        if is_reingest:
            _delete_qdrant_book_chunks(qdrant_client, QDRANT_COLLECTION, book_hash)
        points = _build_qdrant_points(chunk_payloads, QDRANT_VECTOR_DIM)
        qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)

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
    if is_reingest:
        db.update_book_metadata(book_hash, title, author, epub_path, len(stream))
    else:
        db.add_book(book_hash, title, author, epub_path, len(stream))
    db.add_chapters(chapters_data)

    # Initialize reading state
    if not is_reingest:
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
