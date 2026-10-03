from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox
from PySide6.QtGui import QImage, QPixmap, QFont

class BookDetailsView(QWidget):
    delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_isbn = None
        self.setup_ui()

    def setup_ui(self):
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)

        container = QFrame()
        container.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(15, 15, 15, 15)

        header_layout = QHBoxLayout()
        header_title = QLabel("Book Analytics")
        header_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        header_title.setStyleSheet("border: none;")
        header_layout.addWidget(header_title)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(QSize(24, 24))
        self.close_btn.setStyleSheet("""
            QPushButton { border-radius: 12px; padding: 0px; font-weight: bold; border: 1px solid rgba(255, 255, 255, 0.2); }
            QPushButton:hover { background-color: rgba(255, 85, 85, 0.2); color: #ff5555; }
        """)
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)
        container_layout.addLayout(header_layout)

        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setFixedSize(QSize(160, 220))
        self.cover_label.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px;")
        container_layout.addWidget(self.cover_label, alignment=Qt.AlignCenter)

        self.title_label = QLabel("Select a book to inspect details")
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("border: none; padding-top: 10px;")
        container_layout.addWidget(self.title_label)

        self.author_label = QLabel("")
        self.author_label.setWordWrap(True)
        self.author_label.setAlignment(Qt.AlignCenter)
        self.author_label.setStyleSheet("border: none; font-style: italic; opacity: 0.8;")
        container_layout.addWidget(self.author_label)

        self.isbn_label = QLabel("")
        self.isbn_label.setAlignment(Qt.AlignCenter)
        self.isbn_label.setStyleSheet("border: none; font-family: monospace; font-size: 12px; padding-top: 5px;")
        container_layout.addWidget(self.isbn_label)

        container_layout.addStretch()

        self.delete_btn = QPushButton("🗑| Remove from Shelf")
        self.delete_btn.setObjectName("clearBtn")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        container_layout.addWidget(self.delete_btn)

        layout.addWidget(container)
        self.hide()

    def show_book_details(self, isbn: str, title: str, author: str, cover_bytes: bytes):
        self.current_isbn = isbn
        self.isbn_label.setText(f"ISBN: {isbn}")
        self.title_label.setText(title)
        self.author_label.setText(f"by {author}")

        pixmap = QPixmap()
        if cover_bytes:
            pixmap.loadFromData(cover_bytes)
        else:
            img = QImage(160, 220, QImage.Format_RGB888)
            img.fill(Qt.darkGray)
            pixmap = QPixmap.fromImage(img)

        scaled_pixmap = pixmap.scaled(self.cover_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.cover_label.setPixmap(scaled_pixmap)
        self.show()

    def on_delete_clicked(self):
        if not self.current_isbn:
            return
        confirm = QMessageBox.question(
            self, "Remove Book",
            "Are you sure you want to remove this book from your collection?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.delete_requested.emit(self.current_isbn)
            self.hide()
