from PySide6.QtCore import Qt, QSize, QRect, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QListWidgetItem,
                             QLineEdit)
from PySide6.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPalette
from cover_cache import cover_path, has_cached_cover

class BookshelfView(QWidget):
    book_selected = Signal(str, str, str, str, str, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header Title
        log_title = QLabel("Bookshelf")
        log_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(log_title)

        # The Library Matrix Grid View
        self.grid_widget = QListWidget()
        self.grid_widget.setViewMode(QListWidget.IconMode)
        self.grid_widget.setResizeMode(QListWidget.Adjust)
        self.grid_widget.setSpacing(20)
        self.grid_widget.setIconSize(QSize(110, 132))
        self.grid_widget.setMovement(QListWidget.Static)
        self.grid_widget.setSelectionMode(QListWidget.NoSelection)
        self.grid_widget.setFocusPolicy(Qt.NoFocus)
        self.grid_widget.itemClicked.connect(self.on_item_clicked)
        self.apply_palette_styles()
        layout.addWidget(self.grid_widget)

        # Live Filter Search Field Layout Container
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔎 Type to filter bookshelf by title or author name...")
        self.filter_input.textChanged.connect(self.filter_bookshelf_items)
        filter_layout.addWidget(self.filter_input)
        layout.addLayout(filter_layout)

    def render_book_item(
        self, title: str, author: str, cover_url: str, isbn: str = "",
        publication_date: str = "", publisher: str = "", page_count: int = 0,
    ):
        if cover_url and has_cached_cover(isbn):
            pixmap = QPixmap(str(cover_path(isbn)))
        else:
            pixmap = self._make_placeholder_cover(title, self.palette())

        item = QListWidgetItem()
        item.setIcon(pixmap)
        item.setSizeHint(QSize(120, 142))
        item.setText("")
        item.setToolTip(f"{title}\n{author}")

        item.setData(Qt.UserRole, isbn)
        item.setData(Qt.UserRole + 1, title)
        item.setData(Qt.UserRole + 2, author)
        item.setData(Qt.UserRole + 3, cover_url)
        item.setData(Qt.UserRole + 4, publication_date)
        item.setData(Qt.UserRole + 5, publisher)
        item.setData(Qt.UserRole + 6, page_count)

        self.grid_widget.insertItem(0, item)
        self.filter_bookshelf_items(self.filter_input.text())

    def apply_palette_styles(self, palette=None):
        palette = palette or self.palette()
        base_color = palette.color(QPalette.Base).name()
        self.grid_widget.setStyleSheet(
            f"QListWidget {{ background: {base_color}; border: none; }}"
            "QListWidget::item, QListWidget::item:hover, QListWidget::item:selected, "
            "QListWidget::item:focus { background: transparent; border: none; padding: 5px; }")

        for index in range(self.grid_widget.count()):
            item = self.grid_widget.item(index)
            isbn = str(item.data(Qt.UserRole))
            if not item.data(Qt.UserRole + 3) or not has_cached_cover(isbn):
                item.setIcon(self._make_placeholder_cover(
                    str(item.data(Qt.UserRole + 1)), palette
                ))
            else:
                item.setIcon(QPixmap(str(cover_path(isbn))))

    @staticmethod
    def _make_placeholder_cover(title: str, palette) -> QPixmap:
        placeholder = QImage(108, 130, QImage.Format_RGB888)
        placeholder.fill(palette.color(QPalette.AlternateBase))
        painter = QPainter(placeholder)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(palette.color(QPalette.Mid))
        painter.drawRect(5, 5, 98, 120)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(palette.color(QPalette.Text))
        painter.drawText(
            QRect(10, 15, 88, 100),
            Qt.AlignCenter | Qt.TextWordWrap,
            title[:25] + ("..." if len(title) > 25 else ""),
        )
        painter.end()
        return QPixmap.fromImage(placeholder)

    def filter_bookshelf_items(self, text: str):
        search_query = text.strip().lower()
        for i in range(self.grid_widget.count()):
            item = self.grid_widget.item(i)
            title = str(item.data(Qt.UserRole + 1)).lower()
            author = str(item.data(Qt.UserRole + 2)).lower()
            isbn = str(item.data(Qt.UserRole)).lower()

            if search_query in title or search_query in author or search_query in isbn:
                item.setHidden(False)
            else:
                item.setHidden(True)

    def on_item_clicked(self, item: QListWidgetItem):
        isbn = item.data(Qt.UserRole)
        title = item.data(Qt.UserRole + 1)
        author = item.data(Qt.UserRole + 2)
        cover_url = item.data(Qt.UserRole + 3)
        publication_date = item.data(Qt.UserRole + 4) or ""
        publisher = item.data(Qt.UserRole + 5) or ""
        page_count = item.data(Qt.UserRole + 6) or 0
        if isbn:
            self.book_selected.emit(
                isbn, title, author, cover_url, publication_date, publisher, page_count
            )

    def refresh_item_cover(self, isbn: str):
        for index in range(self.grid_widget.count()):
            item = self.grid_widget.item(index)
            if item.data(Qt.UserRole) == isbn and has_cached_cover(isbn):
                item.setIcon(QPixmap(str(cover_path(isbn))))
                return

    def remove_item_by_isbn(self, isbn: str):
        for i in range(self.grid_widget.count()):
            item = self.grid_widget.item(i)
            if item.data(Qt.UserRole) == isbn:
                self.grid_widget.takeItem(i)
                break

    def clear_ui_grid(self):
        """Called externally by UI orchestrator to clear visual elements."""
        self.filter_input.clear()
        self.grid_widget.clear()
