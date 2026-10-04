import os
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QTimer, Slot, QSettings
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QApplication, QPushButton, QMenu, QMessageBox,
                             QInputDialog, QLineEdit, QLabel)
from PySide6.QtGui import QAction

import database as db
from workers import CameraWorker, FetchBookWorker
from scanner_view import ScannerView
from bookshelf_view import BookshelfView
from book_details_view import BookDetailsView
from sync_worker import ServerHealthCheckWorker, SyncWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setPalette(QApplication.palette())
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("ISBN Book Scanner")
        self.resize(950, 900)
        self.scanned_isbns = set()
        self._active_workers = []
        self.worker = None
        self._sync_worker = None
        self._sync_requested = False
        self._health_worker = None
        self._health_check_pending = False
        self.sync_token = ""
        self.sync_username = ""
        self.settings = QSettings("Bookshelf", "ISBNBookScanner")
        self.sync_server_url = (
            os.environ.get("BOOKSHELF_SYNC_URL")
            or self.settings.value("sync/server_url", "http://127.0.0.1:8000", type=str)
        )

        db.configure_shared_database()
        db.init_db()
        self.setup_ui()
        QApplication.instance().paletteChanged.connect(self.apply_palette_styles)
        self.load_books_from_db()
        self.status_reset_timer = None
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(30000)
        self._health_timer.timeout.connect(self._check_server_connection)
        self._check_server_connection()
        self._health_timer.start()

    def setup_ui(self):
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

        self.sync_connection_indicator = QLabel()
        self.sync_connection_indicator.setObjectName("syncConnectionIndicator")
        self.sync_connection_indicator.setFixedSize(12, 12)
        self.sync_connection_indicator.setToolTip("Checking sync server connection...")
        self.sync_connection_indicator.setAccessibleName("Sync server connection status")
        self.sync_connection_indicator.setStyleSheet(
            "QLabel { background-color: #8a929c; border-radius: 6px; }")
        top_bar_layout.addWidget(self.sync_connection_indicator, alignment=Qt.AlignVCenter)

        # NEW: Settings Button Context Setup (The Cogwheel Menu Button)
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setObjectName("settingsBtn")
        self.setup_settings_menu()
        top_bar_layout.addWidget(self.settings_btn)

        main_layout.addLayout(top_bar_layout)

        self.scanner_view = ScannerView()
        self.bookshelf_view = BookshelfView()
        self.book_details_view = BookDetailsView()

        self.scanner_view.hide()

        shelf_container = QWidget()
        shelf_layout = QHBoxLayout(shelf_container)
        shelf_layout.setContentsMargins(0, 0, 0, 0)
        shelf_layout.addWidget(self.bookshelf_view, stretch=3)
        shelf_layout.addWidget(self.book_details_view, stretch=1)

        main_layout.addWidget(self.scanner_view)
        main_layout.addWidget(shelf_container, stretch=1)

        self.scanner_view.manual_isbn_submitted.connect(self.handle_barcode)
        self.bookshelf_view.book_selected.connect(self.book_details_view.show_book_details)
        self.book_details_view.delete_requested.connect(self.remove_single_book)

        self.apply_palette_styles()

    def apply_palette_styles(self, system_palette=None):
        system_palette = system_palette or QApplication.palette()
        self.setPalette(system_palette)

        window_bg = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.Window).name()
        base_bg = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.Base).name()
        text_color = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.WindowText).name()
        border_color = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.Mid).name()
        highlight_color = system_palette.color(system_palette.ColorGroup.Active, system_palette.ColorRole.Highlight).name()
        highlighted_text_color = system_palette.color(
            system_palette.ColorGroup.Active, system_palette.ColorRole.HighlightedText
        ).name()

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {window_bg}; }}
            QWidget {{ color: {text_color}; font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; }}
            QFrame {{ border: 1px solid {border_color}; border-radius: 8px; background-color: {base_bg}; }}
            QPushButton {{
                background-color: {window_bg}; color: {text_color}; border: 1px solid {highlight_color};
                border-radius: 6px; padding: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {highlight_color}; color: {highlighted_text_color}; }}
            QPushButton#toggleCamBtn {{ background-color: {base_bg}; border: 1px solid {highlight_color}; padding: 8px 15px; margin-bottom: 5px; }}
            QPushButton#toggleCamBtn:hover {{ background-color: {highlight_color}; }}
            QPushButton#settingsBtn {{ background-color: {base_bg}; font-size: 16px; padding: 6px 12px; margin-bottom: 5px; }}
            QPushButton#settingsBtn:hover {{ background-color: {highlight_color}; }}
            QMenu {{ background-color: {base_bg}; border: 1px solid {border_color}; border-radius: 6px; padding: 5px; }}
            QMenu::item {{ padding: 6px 25px 6px 20px; color: {text_color}; }}
            QMenu::item:selected {{ background-color: {highlight_color}; color: {highlighted_text_color}; border-radius: 4px; }}
            QLineEdit {{ background-color: {base_bg}; border: 1px solid {border_color}; border-radius: 6px; padding: 10px; color: {text_color}; font-size: 14px; }}
            QLineEdit:focus {{ border: 1px solid {highlight_color}; }}
            QListWidget {{ background-color: {base_bg}; border: 1px solid {border_color}; border-radius: 8px; }}
        """)
        self.scanner_view.apply_palette_styles(system_palette)
        self.bookshelf_view.apply_palette_styles(system_palette)
        self.book_details_view.apply_palette_styles(system_palette)

    def setup_settings_menu(self):
        """Assembles the dropdown context menu and drops it behind the cogwheel button."""
        self.settings_menu = QMenu(self)

        self.register_action = QAction("Register Sync Account...", self)
        self.register_action.triggered.connect(lambda: self.prompt_sync_auth("register"))
        self.login_action = QAction("Log In to Sync...", self)
        self.login_action.triggered.connect(lambda: self.prompt_sync_auth("login"))
        self.sync_action = QAction("Sync Now", self)
        self.sync_action.setEnabled(False)
        self.sync_action.triggered.connect(self.sync_now)
        self.logout_action = QAction("Log Out of Sync", self)
        self.logout_action.setEnabled(False)
        self.logout_action.triggered.connect(self.logout_sync)

        self.settings_menu.addAction(self.login_action)
        self.settings_menu.addAction(self.sync_action)
        self.settings_menu.addAction(self.logout_action)
        self.settings_menu.addSeparator()
        self.settings_menu.addAction(self.register_action)

        # Bind context dropdown display directly to our custom cog action button anchor
        self.settings_btn.setMenu(self.settings_menu)

    def toggle_scanner_view(self):
        if self.scanner_view.isVisible():
            self.scanner_view.hide()
            self.toggle_cam_btn.setText("📷 Open Scanner Suite")
            self.stop_camera()
        else:
            self.scanner_view.show()
            self.toggle_cam_btn.setText("🙈 Hide Scanner Suite")
            self.setup_camera()

    def setup_camera(self):
        if self.worker is not None and self.worker.isRunning():
            return

        self.worker = CameraWorker()
        self.worker.frame_received.connect(self.scanner_view.update_frame)
        self.worker.barcode_detected.connect(self.handle_barcode)
        self.worker.camera_unavailable.connect(self.handle_camera_unavailable)
        self.worker.start()

    def stop_camera(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

    def handle_camera_unavailable(self, message: str):
        self.scanner_view.set_status(message, "color: #ffaa55; font-weight: bold;")
        self.scanner_view.manual_input.setFocus()

    def prompt_sync_auth(self, operation: str):
        if self._sync_worker is not None and self._sync_worker.isRunning():
            self.statusBar().showMessage("A sync operation is already running.", 5000)
            return

        title = "Register Sync Account" if operation == "register" else "Log In to Sync"
        server_url, accepted = QInputDialog.getText(
            self, title, "Server URL:", text=self.sync_server_url
        )
        if not accepted:
            return

        server_url = server_url.strip().rstrip("/")
        try:
            parsed_url = urlsplit(server_url)
        except ValueError:
            parsed_url = None
        if not parsed_url or parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.hostname:
            QMessageBox.warning(
                self, "Invalid Server URL", "Enter an absolute http:// or https:// server URL."
            )
            return

        username, accepted = QInputDialog.getText(self, title, "Username:")
        if not accepted or not username.strip():
            return

        password, accepted = QInputDialog.getText(
            self, title, "Password:", QLineEdit.Password
        )
        if not accepted or not password:
            return

        self.sync_server_url = server_url
        self.settings.setValue("sync/server_url", server_url)
        self._check_server_connection()
        self.start_sync_worker(operation, username.strip(), password)

    def _check_server_connection(self):
        if self._health_worker is not None and self._health_worker.isRunning():
            self._health_check_pending = True
            return

        worker = ServerHealthCheckWorker(self.sync_server_url)
        worker.connection_checked.connect(
            lambda connected, checked_url=worker.server_url:
                self._set_server_connection_status(connected, checked_url)
        )
        worker.finished.connect(lambda worker=worker: self._finish_health_check(worker))
        self._health_worker = worker
        self._active_workers.append(worker)
        worker.start()

    def _set_server_connection_status(self, connected: bool, checked_url: str):
        if checked_url != self.sync_server_url.rstrip("/"):
            return

        color = "#2f9e62" if connected else "#d64f4f"
        description = "Sync server is reachable" if connected else "Sync server is unreachable"
        self.sync_connection_indicator.setStyleSheet(
            f"QLabel {{ background-color: {color}; border-radius: 6px; }}")
        self.sync_connection_indicator.setToolTip(description)
        self.sync_connection_indicator.setAccessibleDescription(description)

    def _finish_health_check(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if self._health_worker is worker:
            self._health_worker = None
        worker.deleteLater()

        url_changed = worker.server_url != self.sync_server_url.rstrip("/")
        if self._health_check_pending or url_changed:
            self._health_check_pending = False
            self._check_server_connection()

    def start_sync_worker(self, operation: str, username="", password="", token=""):
        if self._sync_worker is not None and self._sync_worker.isRunning():
            self._sync_requested = True
            return

        worker = SyncWorker(
            operation,
            self.sync_server_url,
            username=username or self.sync_username,
            password=password,
            token=token or self.sync_token,
        )
        worker.auth_succeeded.connect(self.on_sync_authenticated)
        worker.auth_failed.connect(self.on_sync_failed)
        worker.sync_succeeded.connect(self.on_sync_succeeded)
        worker.sync_failed.connect(self.on_sync_failed)
        worker.finished.connect(lambda: self.on_sync_worker_finished(worker))
        self._sync_worker = worker
        self.statusBar().showMessage("Synchronizing bookshelf...")
        worker.start()

    def on_sync_authenticated(self, token: str, username: str):
        self.sync_token = token
        self.sync_username = username
        self.sync_action.setEnabled(True)
        self.logout_action.setEnabled(True)
        self.statusBar().showMessage(f"Signed in to sync as {username}.", 5000)

    def on_sync_succeeded(self, downloaded, removed, uploaded: int, deleted: int):
        for isbn, title, author, cover_bytes in downloaded:
            self.scanned_isbns.add(isbn)
            self.bookshelf_view.remove_item_by_isbn(isbn)
            self.bookshelf_view.render_book_item(title, author, cover_bytes, isbn)

        for isbn in removed:
            self.scanned_isbns.discard(isbn)
            self.bookshelf_view.remove_item_by_isbn(isbn)
            if self.book_details_view.current_isbn == isbn:
                self.book_details_view.current_isbn = None
                self.book_details_view.hide()

        self.statusBar().showMessage(
            f"Sync complete: {len(downloaded)} downloaded, {len(removed)} removed, "
            f"{uploaded} uploaded, {deleted} deletes sent.",
            10000,
        )

    def on_sync_failed(self, message: str):
        self._sync_requested = False
        self.statusBar().showMessage(f"Sync failed: {message}", 15000)

    def on_sync_worker_finished(self, worker):
        if self._sync_worker is worker:
            self._sync_worker = None
        worker.deleteLater()
        if self._sync_requested and self.sync_token:
            self._sync_requested = False
            self.start_sync_worker("sync")

    def sync_now(self):
        if not self.sync_token:
            self.statusBar().showMessage("Log in before synchronizing.", 5000)
            return
        self.start_sync_worker("sync")

    def logout_sync(self):
        if self._sync_worker is not None and self._sync_worker.isRunning():
            self.statusBar().showMessage("Wait for the current sync to finish before logging out.", 5000)
            return
        self.sync_token = ""
        self.sync_username = ""
        self.sync_action.setEnabled(False)
        self.logout_action.setEnabled(False)
        self.statusBar().showMessage("Signed out of sync.", 5000)

    def load_books_from_db(self):
        rows = db.get_all_books()
        for row in rows:
            isbn, title, author, _engine_source, cover_blob = row
            self.scanned_isbns.add(isbn)
            self.bookshelf_view.render_book_item(title, author, cover_blob, isbn)

    @Slot(str)
    def handle_barcode(self, isbn: str):
        # Kill any pending text resets so they don't overwrite current status updates
        if self.status_reset_timer and self.status_reset_timer.isActive():
            self.status_reset_timer.stop()

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

            # Use a reusable single shot timer instance rather than an un-trackable lambda closure
            self.status_reset_timer = QTimer()
            self.status_reset_timer.setSingleShot(True)
            self.status_reset_timer.timeout.connect(
                lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book")
            )
            self.status_reset_timer.start(2000)

    @Slot(str, str, str, bytes)
    def save_and_render_book(self, isbn: str, title: str, author: str, cover_bytes: bytes):
        if self.status_reset_timer and self.status_reset_timer.isActive():
            self.status_reset_timer.stop()

        db.save_book(isbn, title, author, cover_bytes)
        self.bookshelf_view.render_book_item(title, author, cover_bytes, isbn)
        if self.sync_token:
            self.start_sync_worker("sync")
        self.scanner_view.set_status(f"✅ Logged: {title}")
        self.book_details_view.show_book_details(isbn, title, author, cover_bytes)

        self.status_reset_timer = QTimer()
        self.status_reset_timer.setSingleShot(True)
        self.status_reset_timer.timeout.connect(
            lambda: self.scanner_view.set_status("Center an ISBN barcode to log a book")
        )
        self.status_reset_timer.start(2500)

    def remove_single_book(self, isbn: str):
        if isbn in self.scanned_isbns:
            self.scanned_isbns.remove(isbn)
        db.delete_book_by_isbn(isbn)
        self.bookshelf_view.remove_item_by_isbn(isbn)
        if self.sync_token:
            self.start_sync_worker("sync")
        self.scanner_view.set_status("🗑️ Book removed from collection.")

    def _cleanup_worker(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def closeEvent(self, event):
        if self._sync_worker is not None and self._sync_worker.isRunning():
            self._sync_worker.stop()
            self._sync_worker.wait()
        self.stop_camera()
        for w in self._active_workers:
            w.quit()
            w.wait()
        event.accept()
