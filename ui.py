from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter

import database as db
from workers import CameraWorker, FetchBookWorker
from scanner_view import ScannerView
from bookshelf_view import BookshelfView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibeScan Studio - Split Architecture")
        self.resize(800, 900)
        self.scanned_isbns = set()
        self._active_workers = []

        db.init_db()
        self.setup_ui()
        self.load_books_from_db()
        self.setup_camera()
        self.setup_laser_timer()

    def setup_ui(self):
        # Master centralized stylesheet definitions
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

        splitter = QSplitter(Qt.Vertical)

        # Instantiating our newly decoupled custom visual sub-widgets
        self.scanner_view = ScannerView()
        self.bookshelf_view = BookshelfView()

        # Connect signals passing out of sub-widgets to main window controller slots
        self.scanner_view.manual_isbn_submitted.connect(self.handle_barcode)
        self.bookshelf_view.clear_library_requested.connect(self.wipe_all_data)

        # Assemble layout architecture onto the central control panel
        splitter.addWidget(self.scanner_view)
        splitter.addWidget(self.bookshelf_view)
        splitter.setSizes([380, 520])
        main_layout.addWidget(splitter)

    def setup_camera(self):
        self.worker = CameraWorker()
        # Route background video frames straight down to the dedicated display widget
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
            self.bookshelf_view.render_book_item(title, author, cover_blob)

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
        self.bookshelf_view.render_book_item(title, author, cover_bytes)
        self.scanner_view.set_status(f"✅ Logged: {title}", "color: #a6e3a1;")
        QTimer.singleShot(2500, lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book", "color: #a6e3a1;"))

    def wipe_all_data(self):
        self.scanned_isbns.clear()
        db.clear_all_books()
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
