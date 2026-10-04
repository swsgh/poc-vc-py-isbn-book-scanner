from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox
from PySide6.QtGui import QImage, QPixmap, QFont, QPalette


class BookDetailsView(QWidget):
    delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_isbn = None
        self.current_title = ""
        self.current_cover_bytes = b""
        self.setup_ui()

    def setup_ui(self):
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)

        self.container = QFrame(self)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(15, 15, 15, 15)

        header_layout = QHBoxLayout()
        header_title = QLabel("Book Analytics", self.container)
        header_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        header_title.setStyleSheet("border: none;")
        header_layout.addWidget(header_title)

        self.close_btn = QPushButton("✕", self.container)
        self.close_btn.setFixedSize(QSize(24, 24))
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)
        container_layout.addLayout(header_layout)

        self.cover_label = QLabel(self.container)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setFixedSize(QSize(160, 220))
        container_layout.addWidget(self.cover_label, alignment=Qt.AlignCenter)

        self.title_label = QLabel("Select a book to inspect details", self.container)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("border: none; padding-top: 10px;")
        container_layout.addWidget(self.title_label)

        self.author_label = QLabel("", self.container)
        self.author_label.setWordWrap(True)
        self.author_label.setAlignment(Qt.AlignCenter)
        self.author_label.setStyleSheet("border: none; font-style: italic;")
        container_layout.addWidget(self.author_label)

        self.isbn_label = QLabel("", self.container)
        self.isbn_label.setAlignment(Qt.AlignCenter)
        self.isbn_label.setStyleSheet(
            "border: none; font-family: monospace; font-size: 12px; padding-top: 5px;"
        )
        container_layout.addWidget(self.isbn_label)
        container_layout.addStretch()

        self.delete_btn = QPushButton("🗑| Remove from Shelf", self.container)
        self.delete_btn.setObjectName("clearBtn")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        container_layout.addWidget(self.delete_btn)

        layout.addWidget(self.container)
        self.apply_palette_styles()
        self.hide()

    def apply_palette_styles(self, palette=None):
        palette = palette or self.palette()
        border_color = palette.color(QPalette.Mid).name()
        base_color = palette.color(QPalette.Base).name()
        button_color = palette.color(QPalette.Button).name()
        button_text = palette.color(QPalette.ButtonText).name()
        highlight_color = palette.color(QPalette.Highlight).name()
        highlighted_text = palette.color(QPalette.HighlightedText).name()

        self.container.setStyleSheet(
            f"QFrame {{ background-color: {base_color}; border: 1px solid {border_color}; "
            "border-radius: 8px; }"
        )
        self.cover_label.setStyleSheet(
            f"border: 1px solid {border_color}; border-radius: 6px;"
        )
        self.close_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 12px; padding: 0px; font-weight: bold; "
            f"border: 1px solid {border_color}; }}"
            "QPushButton:hover { background-color: rgba(255, 85, 85, 0.2); color: #ff5555; }"
        )
        self.delete_btn.setStyleSheet(
            f"QPushButton {{ background-color: {button_color}; color: {button_text}; "
            f"border: 1px solid {border_color}; border-radius: 6px; padding: 10px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {highlight_color}; color: {highlighted_text}; }}"
        )
        if self.current_isbn and not self.current_cover_bytes:
            self._show_placeholder_cover(palette)

    def _show_placeholder_cover(self, palette=None):
        palette = palette or self.palette()
        image = QImage(160, 220, QImage.Format_RGB888)
        image.fill(palette.color(QPalette.AlternateBase))
        self.cover_label.setPixmap(QPixmap.fromImage(image))

    def show_book_details(self, isbn: str, title: str, author: str, cover_bytes: bytes):
        self.current_isbn = isbn
        self.current_title = title
        self.current_cover_bytes = cover_bytes
        self.isbn_label.setText(f"ISBN: {isbn}")
        self.title_label.setText(title)
        self.author_label.setText(f"by {author}")

        pixmap = QPixmap()
        if cover_bytes:
            pixmap.loadFromData(cover_bytes)
        else:
            palette = self.palette()
            self._show_placeholder_cover(palette)
            pixmap = self.cover_label.pixmap()

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
