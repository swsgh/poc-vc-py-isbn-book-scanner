from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
    QDialog, QSizePolicy,
)
from PySide6.QtGui import QPixmap, QFont, QPalette
from cover_cache import cover_path, has_cached_cover


class ClickableCoverLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CoverZoomDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self._source_pixmap = pixmap
        self.setModal(True)
        self.setStyleSheet("QDialog { background-color: rgba(16, 16, 16, 235); }")
        if parent:
            self.setGeometry(parent.geometry())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        header = QHBoxLayout()
        header.addStretch()
        close_button = QPushButton("×", self)
        close_button.setAccessibleName("Close enlarged cover")
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        layout.addLayout(header)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        layout.addWidget(self.image_label, stretch=1)
        self._update_cover_pixmap()
        if parent:
            self.setFixedSize(parent.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_cover_pixmap()

    def _update_cover_pixmap(self):
        if not self._source_pixmap.isNull() and hasattr(self, "image_label"):
            self.image_label.setPixmap(self._source_pixmap.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))


class BookDetailsView(QWidget):
    delete_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_isbn = None
        self.current_title = ""
        self.current_cover_url = ""
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

        self.cover_label = ClickableCoverLabel(self.container)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setFixedSize(QSize(200, 275))
        self.cover_label.setCursor(Qt.PointingHandCursor)
        self.cover_label.clicked.connect(self.show_cover_overlay)
        container_layout.addWidget(self.cover_label, alignment=Qt.AlignCenter)

        self.title_label = QLabel("Select a book to inspect details", self.container)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.title_label.setStyleSheet("border: none; padding-top: 10px;")
        container_layout.addWidget(self.title_label)

        self.author_label = QLabel("", self.container)
        self.author_label.setWordWrap(True)
        self.author_label.setAlignment(Qt.AlignCenter)
        self.author_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.author_label.setStyleSheet("border: none; font-style: italic;")
        container_layout.addWidget(self.author_label)

        self.metadata_label = QLabel("", self.container)
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setAlignment(Qt.AlignCenter)
        self.metadata_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        self.metadata_label.setStyleSheet("border: none;")
        self.metadata_label.hide()
        container_layout.addWidget(self.metadata_label)

        self.isbn_label = QLabel("", self.container)
        self.isbn_label.setAlignment(Qt.AlignCenter)
        self.isbn_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
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
        if self.current_isbn and not has_cached_cover(self.current_isbn):
            self._show_placeholder_cover(palette)

    def _show_placeholder_cover(self, palette=None):
        palette = palette or self.palette()
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText(self.current_title or "Cover unavailable")
        self.cover_label.setWordWrap(True)
        self.cover_label.setStyleSheet(
            "QLabel {"
            f"color: {palette.color(QPalette.Text).name()}; "
            f"background-color: {palette.color(QPalette.Base).name()}; "
            f"border: 1px solid {palette.color(QPalette.Mid).name()}; "
            "border-radius: 6px; padding: 20px; font-weight: bold;"
            "}"
        )

    def show_book_details(
        self, isbn: str, title: str, author: str, cover_url: str,
        publication_date: str = "", publisher: str = "", page_count: int = 0,
    ):
        self.current_isbn = isbn
        self.current_title = title
        self.current_cover_url = cover_url
        self.isbn_label.setText(f"ISBN: {isbn}")
        self.title_label.setText(title)
        self.author_label.setText(author)
        metadata = []
        if publication_date:
            metadata.append(f"First published: {publication_date}")
        if publisher:
            metadata.append(f"Publisher: {publisher}")
        if page_count:
            metadata.append(f"Pages: {page_count}")
        self.metadata_label.setText("\n".join(metadata))
        self.metadata_label.setVisible(bool(metadata))

        if cover_url and has_cached_cover(isbn):
            pixmap = QPixmap(str(cover_path(isbn)))
            self.cover_label.setText("")
            self.cover_label.setPixmap(pixmap.scaled(
                self.cover_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        else:
            self._show_placeholder_cover(self.palette())
        self.show()

    def refresh_cover(self):
        if self.current_isbn and self.current_cover_url and has_cached_cover(self.current_isbn):
            pixmap = QPixmap(str(cover_path(self.current_isbn)))
            self.cover_label.setText("")
            self.cover_label.setPixmap(pixmap.scaled(
                self.cover_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))

    def show_cover_overlay(self):
        if not self.current_isbn or not has_cached_cover(self.current_isbn):
            return
        pixmap = QPixmap(str(cover_path(self.current_isbn)))
        if pixmap.isNull():
            return
        dialog = CoverZoomDialog(pixmap, self.window())
        dialog.exec()

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
