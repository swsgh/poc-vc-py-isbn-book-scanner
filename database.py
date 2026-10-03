import sqlite3

DB_NAME = "books.db"

def init_db():
    """Initializes the local SQLite database to store book metadata and cover images."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            isbn TEXT PRIMARY KEY,
            title TEXT,
            author TEXT,
            cover_blob BLOB
        )
    """)
    conn.commit()
    conn.close()

def save_book(isbn: str, title: str, author: str, cover_bytes: bytes):
    """Inserts or overwrites a book record in the local database storage."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO books (isbn, title, author, cover_blob) VALUES (?, ?, ?, ?)",
            (isbn, title, author, sqlite3.Binary(cover_bytes))
        )
        conn.commit()
    except Exception as e:
        print(f"[DB Error] Failed to write record: {e}")
    finally:
        conn.close()

def get_all_books():
    """Retrieves all stored books from the shelf database collection rows."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT isbn, title, author, cover_blob FROM books")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_book_by_isbn(isbn: str):
    """Deletes a single book entry from the database matching the exact ISBN key."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM books WHERE isbn = ?", (isbn,))
        conn.commit()
    except Exception as e:
        print(f"[DB Error] Failed to remove record for ISBN {isbn}: {e}")
    finally:
        conn.close()

def clear_all_books():
    """Wipes all rows inside the library books collection database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books")
    conn.commit()
    conn.close()
