import sqlite3

DB_NAME = "books.db"

def init_db():
    """Initializes the local SQLite database to store book data and cover images."""
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

def save_book(isbn, title, author, cover_bytes):
    """Inserts or updates a book entry in the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO books (isbn, title, author, cover_blob) VALUES (?, ?, ?, ?)",
            (isbn, title, author, sqlite3.Binary(cover_bytes))
        )
        conn.commit()
    except Exception as e:
        print(f"Database write error: {e}")
    finally:
        conn.close()

def get_all_books():
    """Retrieves all stored books from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT isbn, title, author, cover_blob FROM books")
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_all_books():
    """Purges the book table entirely."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books")
    conn.commit()
    conn.close()
