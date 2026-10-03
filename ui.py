from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QApplication
from PySide6.QtGui import QPalette, QColor

import database as db
from workers import CameraWorker, FetchBookWorker
from scanner_view import ScannerView
from bookshelf_view import BookshelfView
from book_details_view import BookDetailsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibeScan Studio - System Adaptive Style")
        self.resize(950, 900)
        self.scanned_isbns = set()
        self._active_workers = []

        db.init_db()
        self.setup_ui()
        self.load_books_from_db()
        self.setup_camera()
        self.setup_laser_timer()

    def setup_ui(self):
        # 1. EXTRACT NATIVE SYSTEM DARK PALETTE
        # Automatically pulls standard system dark configurations (Windows Dark, Dark Aqua on macOS, Breeze Dark on KDE)
        system_palette = QApplication.palette()
        self.setPalette(system_palette)

        # 2. SUBTLE COMPLIANT WIDGET COLOR POLISHING
        # We read background/foreground roles from the system color space to style input boxes and list cards.
        window_bg = system_palette.color(QPalette.Window).name()
        base_bg = system_palette.color(QPalette.Base).name()
        text_color = system_palette.color(QPalette.WindowText).name()
        highlight_color = system_palette.color(QPalette.Highlight).name()

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {window_bg}; }}
            QWidget {{ color: {text_color}; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; }}

            /* Frames use system background with clean native highlight border rules */
            QFrame {{ border: 1px solid {window_bg}; border-radius: 8px; background-color: {base_bg}; }}

            /* Buttons inherit system highlight coloring for action states */
            QPushButton {{
                background-color: {window_bg}; color: {text_color}; border: 1px solid {highlight_color};
                border-radius: 6px; padding: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {highlight_color}; color: #ffffff; }}

            /* Specific style rules for the destructive action button */
            QPushButton#clearBtn {{ border: 1px solid #ff5555; color: #ff5555; }}
            QPushButton#clearBtn:hover {{ background-color: #ff5555; color: #ffffff; }}

            /* Fields match the exact system base colors */
            QLineEdit {{
                background-color: {window_bg}; border: 1px solid {window_bg};
                border-radius: 6px; padding: 10px; color: {text_color}; font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {highlight_color}; }}

            QListWidget {{ background-color: {base_bg}; border: 1px solid {window_bg}; border-radius: 8px; }}
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        vertical_splitter = QSplitter(Qt.Vertical)

        # Instantiating decoupled custom visual sub-widgets
        self.scanner_view = ScannerView()
        self.bookshelf_view = BookshelfView()

        # Lower block layout setup
        shelf_container = QWidget()
        shelf_layout = QHBoxLayout(shelf_container)
        shelf_layout.setContentsMargins(0, 0, 0, 0)

        self.book_details_view = BookDetailsView()

        shelf_layout.addWidget(self.bookshelf_view, stretch=3)
        shelf_layout.addWidget(self.book_details_view, stretch=1)

        # Assemble elements on control layout trees
        vertical_splitter.addWidget(self.scanner_view)
        vertical_splitter.addWidget(shelf_container)

        # FIXED: Pass a standard layout list boundary definition to allocate initial workspace sizes
        vertical_splitter.setSizes([380, 520])
        main_layout.addWidget(vertical_splitter)

        # Inter-widget signal connections
        self.scanner_view.manual_isbn_submitted.connect(self.handle_barcode)
        self.bookshelf_view.clear_library_requested.connect(self.wipe_all_data)
        self.bookshelf_view.book_selected.connect(self.book_details_view.show_book_details)
        self.book_details_view.delete_requested.connect(self.remove_single_book)

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
            QTimer.singleShot(2000, lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book"))

    @Slot(str, str, str, bytes)
    def save_and_render_book(self, isbn, title, author, cover_bytes):
        db.save_book(isbn, title, author, cover_bytes)
        self.bookshelf_view.render_book_item(title, author, cover_bytes, isbn)
        self.scanner_view.set_status(f"✅ Logged: {title}")

        self.book_details_view.show_book_details(isbn, title, author, cover_bytes)
        QTimer.singleShot(2500, lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book"))

    def remove_single_book(self, isbn):
        if isbn in self.scanned_isbns:
            self.scanned_isbns.remove(isbn)
        db.delete_book_by_isbn(isbn)
        self.bookshelf_view.remove_item_by_isbn(isbn)
        self.scanner_view.set_status("🗑️ Book removed from collection.")

    def wipe_all_data(self):
        self.scanned_isbns.clear()
        db.clear_all_books()
        self.book_details_view.hide()
        self.scanner_view.set_status("🧹 Library database completely wiped.")

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
