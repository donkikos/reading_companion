import os
import spacy
import chromadb
import hashlib
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import db

# Initialize Spacy and ChromaDB
nlp = spacy.load("en_core_web_sm")
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
    for block in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'br']):
        block.append(' ')
    return soup.get_text()

def extract_sentences(text):
    """Split text into sentences using Spacy."""
    doc = nlp(text)
    # Filter out very short or empty sentences
    return [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 5]

def ingest_epub(epub_path, progress_callback=None):
    """Parse EPUB, tokenize sentences, and store in ChromaDB & SQLite."""
    print(f"Ingesting: {epub_path}")
    
    # 1. Hashing and Deduplication
    if progress_callback: progress_callback("Hashing...", 0)
    book_hash = get_file_hash(epub_path)
    
    existing = db.get_book(book_hash)
    if existing:
        print(f"Book already exists: {existing['title']} ({book_hash})")
        if progress_callback: progress_callback("Done", 100)
        return book_hash

    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"Error reading EPUB: {e}")
        raise e

    # Metadata
    title = book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else "Unknown Title"
    author = book.get_metadata('DC', 'creator')[0][0] if book.get_metadata('DC', 'creator') else "Unknown Author"
    
    print(f"Processing '{title}' by {author}")

    # Chroma Collection
    collection = chroma_client.get_or_create_collection(name="library")

    seq_id = 0
    chapter_index = 0
    
    chapters_data = [] # For SQL
    
    # Batch storage
    ids = []
    documents = []
    metadatas = []
    
    # Count total items for progress
    spine_items = [item for item in book.spine if book.get_item_with_id(item[0])]
    total_items = len(spine_items)
    processed_items = 0

    # Iterate Spine for correct order
    for item_id, linear in book.spine:
        item = book.get_item_with_id(item_id)
        
        if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
            
        # Chapter Start
        start_seq = seq_id
        
        # Parse Text
        raw_content = item.get_content()
        text = clean_html(raw_content)
        sentences = extract_sentences(text)
        
        # Skip empty chapters
        if not sentences:
            processed_items += 1
            continue

        # Try to guess chapter title (simplistic)
        chapter_title = f"Chapter {chapter_index + 1}"
        soup = BeautifulSoup(raw_content, "html.parser")
        h1 = soup.find('h1')
        if h1:
            chapter_title = h1.get_text().strip()
        
        for sentence in sentences:
            ids.append(f"{book_hash}_{seq_id}")
            documents.append(sentence)
            metadatas.append({
                "book_hash": book_hash,
                "seq_id": seq_id,
                "chapter_index": chapter_index
            })
            seq_id += 1
            
            if len(ids) >= 500:
                collection.add(ids=ids, documents=documents, metadatas=metadatas)
                ids = []
                documents = []
                metadatas = []
        
        # Chapter End (seq_id is now at the *next* available, so end is seq_id - 1)
        end_seq = seq_id - 1
        
        chapters_data.append((book_hash, chapter_index, chapter_title, start_seq, end_seq))
        # print(f"  Processed {chapter_title}: Seq {start_seq}-{end_seq}")
        
        chapter_index += 1
        processed_items += 1
        if progress_callback and total_items > 0:
            percent = int((processed_items / total_items) * 100)
            progress_callback(f"Processing {chapter_title}", percent)

    # Flush remaining
    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)

    # 2. Store in SQLite
    db.add_book(book_hash, title, author, epub_path, seq_id)
    db.add_chapters(chapters_data)
    
    # Initialize reading state
    db.update_cursor(book_hash, 0)
    
    if progress_callback: progress_callback("Completed", 100)

    print(f"Finished ingesting. ID: {book_hash}. Total sequences: {seq_id}")
    return book_hash

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ingest_epub(sys.argv[1])
    else:
        print("Usage: python ingest.py <path_to_epub>")