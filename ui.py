from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter

import database as db
from workers import CameraWorker, FetchBookWorker
from scanner_view import ScannerView
from bookshelf_view import BookshelfView
from book_details_view import BookDetailsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibeScan Studio - Dashboard Architecture")
        self.resize(950, 900)  # Width bumped up to handle side-by-side panels seamlessly
        self.scanned_isbns = set()
        self._active_workers = []

        db.init_db()
        self.setup_ui()
        self.load_books_from_db()
        self.setup_camera()
        self.setup_laser_timer()

    def setup_ui(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QWidget { color: #cdd6f4; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton {
                background-color: #f5c2e7; color: #11111b; border-radius: 6px;
                padding: 10px; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #cba6f7; }
            QPushButton#manualBtn { background-color: #89b4fa; min-width: 100px; }
            QPushButton#manualBtn:hover { background-color: #b4befe; }
            QPushButton#exportBtn { background-color: #a6e3a1; }
            QPushButton#exportBtn:hover { background-color: #94e2d5; }
            QPushButton#clearBtn { background-color: #f38ba8; }
            QPushButton#clearBtn:hover { background-color: #eba0ac; }
            QLineEdit {
                background-color: #11111b; border: 1px solid #45475a;
                border-radius: 6px; padding: 10px; color: #cdd6f4; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #f5c2e7; }
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        vertical_splitter = QSplitter(Qt.Vertical)

        # Upper block setup: Camera tracking suite
        self.scanner_view = ScannerView()
        vertical_splitter.addWidget(self.scanner_view)

        # Lower block setup: Bookshelf grid alongside the new inspector panel widget
        shelf_container = QWidget()
        shelf_layout = QHBoxLayout(shelf_container)
        shelf_layout.setContentsMargins(0, 0, 0, 0)

        self.bookshelf_view = BookshelfView()
        self.book_details_view = BookDetailsView()

        shelf_layout.addWidget(self.bookshelf_view, stretch=3)
        shelf_layout.addWidget(self.book_details_view, stretch=1)
        vertical_splitter.addWidget(shelf_container)

        # Inter-widget signals and slots bindings
        self.scanner_view.manual_isbn_submitted.connect(self.handle_barcode)
        self.bookshelf_view.clear_library_requested.connect(self.wipe_all_data)
        self.bookshelf_view.book_selected.connect(self.book_details_view.show_book_details)
        self.book_details_view.delete_requested.connect(self.remove_single_book)

        vertical_splitter.setSizes([380, 520])
        main_layout.addWidget(vertical_splitter)

    def setup_camera(self):
        self.worker = CameraWorker()
        self.worker.frame_received.connect(self.scanner_view.update_frame)
        self.worker.barcode_detected.connect(self.handle_barcode)
        self.worker.start()

    def setup_laser_timer(self):
        self.laser_timer = QTimer(self)
        self.laser_timer.timeout.connect(self.scanner_view.animate_laser)
        self.laser_timer.start(16)

    def load_books_from_db(self):
        rows = db.get_all_books()
        for row in rows:
            isbn, title, author, cover_blob = row
            self.scanned_isbns.add(isbn)
            self.bookshelf_view.render_book_item(title, author, cover_blob, isbn)

    @Slot(str)
    def handle_barcode(self, isbn):
        if isbn not in self.scanned_isbns:
            self.scanned_isbns.add(isbn)
            self.scanner_view.set_status(f"🔍 Digging up metadata for ISBN: {isbn}...")

            fetcher = FetchBookWorker(isbn)
            fetcher.book_fetched.connect(self.save_and_render_book)
            fetcher.finished.connect(lambda: self._cleanup_worker(fetcher))
            self._active_workers.append(fetcher)
            fetcher.start()
        else:
            self.scanner_view.set_status(f"💡 ISBN {isbn} already exists on shelf.", "color: #fab387;")
            QTimer.singleShot(2000, lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book", "color: #a6e3a1;"))

    @Slot(str, str, str, bytes)
    def save_and_render_book(self, isbn, title, author, cover_bytes):
        db.save_book(isbn, title, author, cover_bytes)
        self.bookshelf_view.render_book_item(title, author, cover_bytes, isbn)
        self.scanner_view.set_status(f"✅ Logged: {title}", "color: #a6e3a1;")

        # Proactively fire details update on the sidebar for immediate inspection
        self.book_details_view.show_book_details(isbn, title, author, cover_bytes)
        QTimer.singleShot(2500, lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book", "color: #a6e3a1;"))

    def wipe_all_data(self):
        self.scanned_isbns.clear()
        db.clear_all_books()
        self.book_details_view.hide()
        self.scanner_view.set_status("🧹 Library database completely wiped.", "color: #f38ba8;")

    def _cleanup_worker(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def closeEvent(self, event):
        self.laser_timer.stop()
        self.worker.stop()
        for w in self._active_workers:
            w.quit()
            w.wait()
        event.accept()

    def remove_single_book(self, isbn):
        """Drops targeted entry records across internal memory caches, SQLite storage blocks, and layouts."""
        if isbn in self.scanned_isbns:
            self.scanned_isbns.remove(isbn)

        db.delete_book_by_isbn(isbn)
        self.bookshelf_view.remove_item_by_isbn(isbn)
        self.scanner_view.set_status("🗑️ Book removed from collection.", "color: #f38ba8;")
