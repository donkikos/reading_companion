import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, ".data", "state.db")


def init_db():
    """Ensure the database and tables exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # Books Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            hash TEXT PRIMARY KEY,
            title TEXT,
            author TEXT,
            filepath TEXT,
            total_sequences INTEGER
        )
    """
    )

    # Chapters Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_hash TEXT,
            chapter_index INTEGER,
            title TEXT,
            start_seq_id INTEGER,
            end_seq_id INTEGER,
            FOREIGN KEY(book_hash) REFERENCES books(hash)
        )
    """
    )

    # Reading State Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reading_state (
            book_hash TEXT PRIMARY KEY,
            current_seq_id INTEGER,
            last_updated TIMESTAMP,
            last_cfi TEXT,
            FOREIGN KEY(book_hash) REFERENCES books(hash)
        )
    """
    )

    conn.commit()
    conn.close()


def add_book(book_hash, title, author, filepath, total_sequences):
    """Register a new book."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO books (hash, title, author, filepath, total_sequences)
        VALUES (?, ?, ?, ?, ?)
    """,
        (book_hash, title, author, filepath, total_sequences),
    )
    conn.commit()
    conn.close()


def add_chapters(chapters_data):
    """
    Bulk insert chapters.
    chapters_data: list of tuples (book_hash, index, title, start, end)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO chapters (book_hash, chapter_index, title, start_seq_id, end_seq_id)
        VALUES (?, ?, ?, ?, ?)
    """,
        chapters_data,
    )
    conn.commit()
    conn.close()


def update_cursor(book_hash, seq_id, cfi=None):
    """Update the current reading position for a book."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    if cfi:
        cursor.execute(
            """
            INSERT INTO reading_state (book_hash, current_seq_id, last_updated, last_cfi)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(book_hash) DO UPDATE SET
                current_seq_id = excluded.current_seq_id,
                last_updated = excluded.last_updated,
                last_cfi = excluded.last_cfi
        """,
            (book_hash, seq_id, now, cfi),
        )
    else:
        cursor.execute(
            """
            INSERT INTO reading_state (book_hash, current_seq_id, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(book_hash) DO UPDATE SET
                current_seq_id = excluded.current_seq_id,
                last_updated = excluded.last_updated
        """,
            (book_hash, seq_id, now),
        )
    conn.commit()
    conn.close()


def get_cursor(book_hash):
    """Retrieve the current reading position for a book."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT current_seq_id FROM reading_state WHERE book_hash = ?", (book_hash,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def get_book(book_hash):
    """Get book metadata."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM books WHERE hash = ?", (book_hash,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_books():
    """List all books with their current reading position and chapter."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            b.*, 
            COALESCE(rs.current_seq_id, 0) as current_pos,
            rs.last_cfi,
            c.title as chapter_title,
            c.chapter_index
        FROM books b
        LEFT JOIN reading_state rs ON b.hash = rs.book_hash
        LEFT JOIN chapters c ON b.hash = c.book_hash 
             AND rs.current_seq_id BETWEEN c.start_seq_id AND c.end_seq_id
    """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_chapter(book_hash, seq_id):
    """Find which chapter a sequence ID belongs to."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM chapters 
        WHERE book_hash = ? AND ? BETWEEN start_seq_id AND end_seq_id
    """,
        (book_hash, seq_id),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_chapters_list(book_hash):
    """Get all chapters for a book."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM chapters WHERE book_hash = ? ORDER BY chapter_index ASC",
        (book_hash,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_book_path(book_hash, new_path):
    """Update the filesystem path for a book."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE books SET filepath = ? WHERE hash = ?", (new_path, book_hash)
    )
    conn.commit()
    conn.close()


def get_book_details(book_hash):
    """Get detailed status for a single book."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            b.*, 
            COALESCE(rs.current_seq_id, 0) as current_pos,
            rs.last_cfi,
            c.title as chapter_title,
            c.chapter_index
        FROM books b
        LEFT JOIN reading_state rs ON b.hash = rs.book_hash
        LEFT JOIN chapters c ON b.hash = c.book_hash 
             AND rs.current_seq_id BETWEEN c.start_seq_id AND c.end_seq_id
        WHERE b.hash = ?
    """,
        (book_hash,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


if __name__ == "__main__":
    # For dev: init
    init_db()
    print(f"Database initialized at {DB_PATH}")
