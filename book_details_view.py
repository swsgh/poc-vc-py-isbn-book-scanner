from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtGui import QImage, QPixmap, QFont

class BookDetailsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        # Explicit width restriction to behave like a sidebar
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)

        # Border wrapper framework container
        container = QFrame()
        container.setStyleSheet("background-color: #11111b; border: 1px solid #45475a; border-radius: 8px;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(15, 15, 15, 15)

        # Header Row Layout containing title and close button
        header_layout = QHBoxLayout()
        header_title = QLabel("Book Analytics")
        header_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        header_title.setStyleSheet("border: none; color: #f5c2e7;")
        header_layout.addWidget(header_title)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(QSize(24, 24))
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244; color: #cdd6f4; border-radius: 12px;
                padding: 0px; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #f38ba8; color: #11111b; }
        """)
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)
        container_layout.addLayout(header_layout)

        # Big Cover Visual Art Box
        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setFixedSize(QSize(160, 220))
        self.cover_label.setStyleSheet("background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px;")
        container_layout.addWidget(self.cover_label, alignment=Qt.AlignCenter)

        # Book Information Labels (Title, Author, ISBN)
        self.title_label = QLabel("Select a book to inspect details")
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("border: none; padding-top: 10px; color: #cdd6f4;")
        container_layout.addWidget(self.title_label)

        self.author_label = QLabel("")
        self.author_label.setWordWrap(True)
        self.author_label.setAlignment(Qt.AlignCenter)
        self.author_label.setStyleSheet("border: none; color: #a6adc8; font-style: italic;")
        container_layout.addWidget(self.author_label)

        self.isbn_label = QLabel("")
        self.isbn_label.setAlignment(Qt.AlignCenter)
        self.isbn_label.setStyleSheet("border: none; color: #89b4fa; font-family: monospace; font-size: 12px; padding-top: 5px;")
        container_layout.addWidget(self.isbn_label)

        container_layout.addStretch() # Push everything up to the top
        layout.addWidget(container)

        # Default state: hidden until someone interacts with the list
        self.hide()

    def show_book_details(self, isbn, title, author, cover_bytes):
        """Populates fields dynamically and slides open the widget window view."""
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
