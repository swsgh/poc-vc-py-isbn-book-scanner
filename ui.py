from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QApplication, QPushButton, QMenu, QMessageBox)
from PySide6.QtGui import QAction

import database as db
from workers import CameraWorker, FetchBookWorker
from scanner_view import ScannerView
from bookshelf_view import BookshelfView
from book_details_view import BookDetailsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibeScan Studio - Dashboard Architecture")
        self.resize(950, 900)
        self.scanned_isbns = set()
        self._active_workers = []

        db.init_db()
        self.setup_ui()
        self.load_books_from_db()
        self.setup_camera()
        self.setup_laser_timer()

    def setup_ui(self):
        system_palette = QApplication.palette()
        self.setPalette(system_palette)

        window_bg = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.Window).name()
        base_bg = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.Base).name()
        text_color = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.WindowText).name()
        highlight_color = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.Highlight).name()

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {window_bg}; }}
            QWidget {{ color: {text_color}; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; }}
            QFrame {{ border: 1px solid {window_bg}; border-radius: 8px; background-color: {base_bg}; }}
            QPushButton {{
                background-color: {window_bg}; color: {text_color}; border: 1px solid {highlight_color};
                border-radius: 6px; padding: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {highlight_color}; color: #ffffff; }}
            QPushButton#toggleCamBtn {{ background-color: {base_bg}; border: 1px solid {highlight_color}; padding: 8px 15px; margin-bottom: 5px; }}
            QPushButton#toggleCamBtn:hover {{ background-color: {highlight_color}; }}

            /* Gear wheel button specific polish styling */
            QPushButton#settingsBtn {{ background-color: {base_bg}; font-size: 16px; padding: 6px 12px; margin-bottom: 5px; }}
            QPushButton#settingsBtn:hover {{ background-color: {highlight_color}; }}

            /* Popup Menu Styling Sheets */
            QMenu {{ background-color: {base_bg}; border: 1px solid {highlight_color}; border-radius: 6px; padding: 5px; }}
            QMenu::item {{ padding: 6px 25px 6px 20px; color: {text_color}; }}
            QMenu::item:selected {{ background-color: #ff5555; color: #ffffff; border-radius: 4px; }}

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

        # Upper control layout bar setup
        top_bar_layout = QHBoxLayout()
        self.toggle_cam_btn = QPushButton("📷 Open Scanner Suite")
        self.toggle_cam_btn.setObjectName("toggleCamBtn")
        self.toggle_cam_btn.clicked.connect(self.toggle_scanner_view)
        top_bar_layout.addWidget(self.toggle_cam_btn)

        top_bar_layout.addStretch() # Separate items perfectly down the axis line

        # NEW: Settings Button Context Setup (The Cogwheel Menu Button)
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setObjectName("settingsBtn")
        self.setup_settings_menu()
        top_bar_layout.addWidget(self.settings_btn)

        main_layout.addLayout(top_bar_layout)

        vertical_splitter = QSplitter(Qt.Vertical)

        self.scanner_view = ScannerView()
        self.bookshelf_view = BookshelfView()
        self.book_details_view = BookDetailsView()

        self.scanner_view.hide()

        shelf_container = QWidget()
        shelf_layout = QHBoxLayout(shelf_container)
        shelf_layout.setContentsMargins(0, 0, 0, 0)
        shelf_layout.addWidget(self.bookshelf_view, stretch=3)
        shelf_layout.addWidget(self.book_details_view, stretch=1)

        vertical_splitter.addWidget(self.scanner_view)
        vertical_splitter.addWidget(shelf_container)

        vertical_splitter.setSizes([250, 650])
        main_layout.addWidget(vertical_splitter)

        self.scanner_view.manual_isbn_submitted.connect(self.handle_barcode)
        self.bookshelf_view.book_selected.connect(self.book_details_view.show_book_details)
        self.book_details_view.delete_requested.connect(self.remove_single_book)

    def setup_settings_menu(self):
        """Assembles the dropdown context menu and drops it behind the cogwheel button."""
        self.settings_menu = QMenu(self)

        # Construct the destructive clear action line entry
        clear_action = QAction("🗑️ Clear Library Database", self)
        clear_action.triggered.connect(self.wipe_all_data)
        self.settings_menu.addAction(clear_action)

        # Bind context dropdown display directly to our custom cog action button anchor
        self.settings_btn.setMenu(self.settings_menu)

    def toggle_scanner_view(self):
        if self.scanner_view.isVisible():
            self.scanner_view.hide()
            self.toggle_cam_btn.setText("📷 Open Scanner Suite")
        else:
            self.scanner_view.show()
            self.toggle_cam_btn.setText("🙈 Hide Scanner Suite")

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
    def handle_barcode(self, isbn: str):
        if isbn not in self.scanned_isbns:
            self.scanned_isbns.add(isbn)
            self.scanner_view.set_status(f"🔍 Digging up metadata for ISBN: {isbn}...")

            fetcher = FetchBookWorker(isbn)
            fetcher.book_fetched.connect(self.save_and_render_book)
            fetcher.finished.connect(lambda: self._cleanup_worker(fetcher))
            self._active_workers.append(fetcher)
            fetcher.start()
        else:
            self.scanner_view.set_status(f"💡 ISBN {isbn} already exists on shelf.", "color: #ffaa55;")
            QTimer.singleShot(2000, lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book"))

    @Slot(str, str, str, bytes)
    def save_and_render_book(self, isbn: str, title: str, author: str, cover_bytes: bytes):
        db.save_book(isbn, title, author, cover_bytes)
        self.bookshelf_view.render_book_item(title, author, cover_bytes, isbn)
        self.scanner_view.set_status(f"✅ Logged: {title}")
        self.book_details_view.show_book_details(isbn, title, author, cover_bytes)
        QTimer.singleShot(2500, lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book"))

    def remove_single_book(self, isbn: str):
        if isbn in self.scanned_isbns:
            self.scanned_isbns.remove(isbn)
        db.delete_book_by_isbn(isbn)
        self.bookshelf_view.remove_item_by_isbn(isbn)
        self.scanner_view.set_status("🗑️ Book removed from collection.")

    def wipe_all_data(self):
        """Wipes matching cache maps, executes pure file purges, and drops visual items."""
        confirm = QMessageBox.question(
            self, "Clear Entire Library?",
            "Are you completely sure you want to purge all books from the database and UI grid view?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.scanned_isbns.clear()
            db.clear_all_books()
            self.bookshelf_view.clear_ui_grid()
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
