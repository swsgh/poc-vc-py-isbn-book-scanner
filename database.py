import sqlite3
from contextlib import contextmanager

DB_NAME = "books.db"


@contextmanager
def _connect():
    connection = sqlite3.connect(DB_NAME)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    """Initializes the local SQLite database to store book metadata and cover images."""
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS books (
                isbn TEXT PRIMARY KEY,
                title TEXT,
                author TEXT,
                cover_blob BLOB
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                isbn TEXT PRIMARY KEY,
                action_type TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                username TEXT PRIMARY KEY,
                checkpoint INTEGER NOT NULL
            )
        """)


def _queue_sync_action(connection, isbn: str, action_type: str):
    connection.execute(
        "INSERT OR REPLACE INTO sync_queue (isbn, action_type) VALUES (?, ?)",
        (isbn, action_type),
    )


def save_book(isbn: str, title: str, author: str, cover_bytes: bytes, queue_sync=True):
    """Inserts or overwrites a book record in the local database storage."""
    try:
        with _connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO books (isbn, title, author, cover_blob) VALUES (?, ?, ?, ?)",
                (isbn, title, author, sqlite3.Binary(cover_bytes)),
            )
            if queue_sync:
                _queue_sync_action(connection, isbn, "UPLOAD")
            return True
    except Exception as e:
        print(f"[DB Error] Failed to write record: {e}")
        return False


def get_all_books():
    """Retrieves all stored books from the shelf database collection rows."""
    with _connect() as connection:
        return connection.execute(
            "SELECT isbn, title, author, cover_blob FROM books"
        ).fetchall()


def get_book_by_isbn(isbn: str):
    with _connect() as connection:
        return connection.execute(
            "SELECT isbn, title, author, cover_blob FROM books WHERE isbn = ?",
            (isbn,),
        ).fetchone()


def delete_book_by_isbn(isbn: str, queue_sync=True):
    """Deletes a single book entry from the database matching the exact ISBN key."""
    try:
        with _connect() as connection:
            connection.execute("DELETE FROM books WHERE isbn = ?", (isbn,))
            if queue_sync:
                _queue_sync_action(connection, isbn, "DELETE")
            return True
    except Exception as e:
        print(f"[DB Error] Failed to remove record for ISBN {isbn}: {e}")
        return False


def clear_all_books(queue_sync=True):
    """Wipes all rows inside the library books collection database."""
    with _connect() as connection:
        if queue_sync:
            rows = connection.execute("SELECT isbn FROM books").fetchall()
            for (isbn,) in rows:
                _queue_sync_action(connection, isbn, "DELETE")
        connection.execute("DELETE FROM books")


def get_pending_sync_actions():
    with _connect() as connection:
        return connection.execute(
            "SELECT isbn, action_type FROM sync_queue ORDER BY isbn"
        ).fetchall()


def remove_pending_sync_action(isbn: str, action_type: str):
    with _connect() as connection:
        connection.execute(
            "DELETE FROM sync_queue WHERE isbn = ? AND action_type = ?",
            (isbn, action_type),
        )


def get_sync_checkpoint(username: str):
    with _connect() as connection:
        row = connection.execute(
            "SELECT checkpoint FROM sync_state WHERE username = ?",
            (username,),
        ).fetchone()
        return row[0] if row else None


def set_sync_checkpoint(username: str, checkpoint: int):
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO sync_state (username, checkpoint) VALUES (?, ?)",
            (username, checkpoint),
        )
