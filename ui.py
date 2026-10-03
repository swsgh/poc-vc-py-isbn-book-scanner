import os
import pandas as pd
from PySide6.QtCore import Qt, QTimer, Slot, QSize
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QListWidget, QSplitter,
                             QFrame, QListWidgetItem, QFileDialog, QMessageBox)
from PySide6.QtGui import QImage, QPixmap, QFont

import database as db
from workers import CameraWorker, FetchBookWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibeScan Studio - Database Book Shelf")
        self.resize(1150, 720)
        self.scanned_isbns = set()
        self._active_workers = []

        db.init_db()
        self.setup_ui()
        self.load_books_from_db()
        self.setup_camera()

    def setup_ui(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QWidget { color: #cdd6f4; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QFrame { border: 1px solid #45475a; border-radius: 8px; background-color: #181825; }
            QPushButton {
                background-color: #f5c2e7; color: #11111b; border-radius: 6px;
                padding: 10px; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #cba6f7; }
            QPushButton#exportBtn { background-color: #a6e3a1; }
            QPushButton#exportBtn:hover { background-color: #94e2d5; }
            QPushButton#clearBtn { background-color: #f38ba8; }
            QPushButton#clearBtn:hover { background-color: #eba0ac; }
            QListWidget { background-color: #11111b; border: 1px solid #45475a; border-radius: 8px; }
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        splitter = QSplitter(Qt.Horizontal)

        # Left Feed Column
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        self.camera_label = QLabel("Initializing Video Feed...")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("background-color: #000000; border-radius: 6px;")
        left_layout.addWidget(self.camera_label, stretch=4)

        self.status_label = QLabel("Center an ISBN barcode to log a book")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 14px;")
        left_layout.addWidget(self.status_label, stretch=0)

        # Right Grid Column
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        log_title = QLabel("Saved Books Shelf Grid")
        log_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        right_layout.addWidget(log_title)

        self.grid_widget = QListWidget()
        self.grid_widget.setViewMode(QListWidget.IconMode)
        self.grid_widget.setResizeMode(QListWidget.Adjust)
        self.grid_widget.setSpacing(15)
        self.grid_widget.setIconSize(QSize(120, 160))
        self.grid_widget.setMovement(QListWidget.Static)
        right_layout.addWidget(self.grid_widget)

        # Footer Buttons
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("📁 Export Data Sheet")
        self.export_btn.setObjectName("exportBtn")
        self.export_btn.clicked.connect(self.export_data)
        btn_layout.addWidget(self.export_btn)

        self.clear_btn = QPushButton("🗑️ Clear Library Grid")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_library)
        btn_layout.addWidget(self.clear_btn)
        right_layout.addLayout(btn_layout)

        splitter.addWidget(left_frame)
        splitter.addWidget(right_frame)
        splitter.setSizes([500, 650])
        main_layout.addWidget(splitter)

    def setup_camera(self):
        self.worker = CameraWorker()
        self.worker.frame_received.connect(self.update_image)
        self.worker.barcode_detected.connect(self.handle_barcode)
        self.worker.start()

    @Slot(QImage)
    def update_image(self, q_img):
        pixmap = QPixmap.fromImage(q_img)
        if not self.camera_label.size().isEmpty():
            scaled_pixmap = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.camera_label.setPixmap(scaled_pixmap)

    def load_books_from_db(self):
        rows = db.get_all_books()
        for row in rows:
            isbn, title, author, cover_blob = row
            self.scanned_isbns.add(isbn)
            self.render_book_item(title, author, cover_blob)

    @Slot(str)
    def handle_barcode(self, isbn):
        if isbn not in self.scanned_isbns:
            self.scanned_isbns.add(isbn)
            self.status_label.setText(f"🔍 Searching database & web for ISBN: {isbn}...")

            fetcher = FetchBookWorker(isbn)
            fetcher.book_fetched.connect(self.save_and_render_book)
            fetcher.finished.connect(lambda: self._cleanup_worker(fetcher))
            self._active_workers.append(fetcher)
            fetcher.start()

    @Slot(str, str, str, bytes)
    def save_and_render_book(self, isbn, title, author, cover_bytes):
        db.save_book(isbn, title, author, cover_bytes)
        self.render_book_item(title, author, cover_bytes)
        self.status_label.setText("✅ Book registered and saved locally!")
        QTimer.singleShot(2500, lambda: self.status_label.setText("Center an ISBN barcode to log a book"))

    def render_book_item(self, title, author, cover_bytes):
        pixmap = QPixmap()
        if cover_bytes:
            pixmap.loadFromData(cover_bytes)
        else:
            img = QImage(120, 160, QImage.Format_RGB888)
            img.fill(Qt.darkGray)
            pixmap = QPixmap.fromImage(img)

        item = QListWidgetItem()
        item.setIcon(pixmap)
        item.setText(f"{title}\n✍️ {author}")
        item.setTextAlignment(Qt.AlignCenter)
        self.grid_widget.insertItem(0, item)

    def export_data(self):
        rows = db.get_all_books()
        if not rows:
            QMessageBox.warning(self, "Export Failed", "There are no books in your database to export yet!")
            return

        df = pd.DataFrame([{"ISBN": r[0], "Title": r[1], "Author": r[2]} for r in rows])
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Book List", os.path.expanduser("~/Desktop"),
            "Excel Spreadsheet (*.xlsx);;CSV Document (*.csv)"
        )

        if file_path:
            try:
                if selected_filter == "Excel Spreadsheet (*.xlsx)":
                    if not file_path.endswith('.xlsx'): file_path += '.xlsx'
                    df.to_excel(file_path, index=False)
                else:
                    if not file_path.endswith('.csv'): file_path += '.csv'
                    df.to_csv(file_path, index=False, encoding='utf-8')
                QMessageBox.information(self, "Success!", f"Library exported cleanly to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Could not write file layout structure:\n{str(e)}")

    def clear_library(self):
        confirm = QMessageBox.question(
            self, "Clear Entire Library?",
            "Are you completely sure you want to purge all books from the database and UI grid view?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.scanned_isbns.clear()
            self.grid_widget.clear()
            db.clear_all_books()
            self.status_label.setText("🧹 Library database completely wiped.")

    def _cleanup_worker(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def closeEvent(self, event):
        self.worker.stop()
        for w in self._active_workers:
            w.quit()
            w.wait()
        event.accept()
