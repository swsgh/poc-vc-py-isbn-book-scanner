import os
import pandas as pd
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QListWidgetItem,
                             QFileDialog, QMessageBox, QLineEdit)
from PySide6.QtGui import QImage, QPixmap, QFont
import database as db

class BookshelfView(QWidget):
    clear_library_requested = Signal()
    book_selected = Signal(str, str, str, bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header Title
        log_title = QLabel("Saved Books Shelf Grid")
        log_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(log_title)

        # The Library Matrix Grid View
        self.grid_widget = QListWidget()
        self.grid_widget.setViewMode(QListWidget.IconMode)
        self.grid_widget.setResizeMode(QListWidget.Adjust)
        self.grid_widget.setSpacing(15)
        self.grid_widget.setIconSize(QSize(100, 140))
        self.grid_widget.setMovement(QListWidget.Static)
        self.grid_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.grid_widget)

        # NEW: Live Filter Search Field Layout Container
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔎 Type to filter bookshelf by title or author name...")
        # Connect text alteration signals to drive our loop filter mechanism instantly
        self.filter_input.textChanged.connect(self.filter_bookshelf_items)
        filter_layout.addWidget(self.filter_input)
        layout.addLayout(filter_layout)

        # Operational Footer Actions Row
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("📁 Export Data Sheet")
        self.export_btn.setObjectName("exportBtn")
        self.export_btn.clicked.connect(self.export_data)
        btn_layout.addWidget(self.export_btn)

        self.clear_btn = QPushButton("🗑️ Clear Library Grid")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.clicked.connect(self.clear_library_action)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

    def render_book_item(self, title: str, author: str, cover_bytes: bytes, isbn: str = ""):
        pixmap = QPixmap()
        if cover_bytes:
            pixmap.loadFromData(cover_bytes)
        else:
            img = QImage(100, 140, QImage.Format_RGB888)
            img.fill(Qt.darkGray)
            pixmap = QPixmap.fromImage(img)

        item = QListWidgetItem()
        item.setIcon(pixmap)
        item.setText(f"{title}\n✍️ {author}")
        item.setTextAlignment(Qt.AlignCenter)

        # Embed key database values inside the UI item element using custom data role flags
        item.setData(Qt.UserRole, isbn)
        item.setData(Qt.UserRole + 1, title)
        item.setData(Qt.UserRole + 2, author)
        item.setData(Qt.UserRole + 3, cover_bytes)

        self.grid_widget.insertItem(0, item)

        # Ensure new items immediately respect any active query filter criteria string
        self.filter_bookshelf_items(self.filter_input.text())

    def filter_bookshelf_items(self, text: str):
        """Iterates over UI components and toggles node visibilities based on query strings."""
        search_query = text.strip().lower()

        for i in range(self.grid_widget.count()):
            item = self.grid_widget.item(i)
            # Pull underlying book parameters out of data cache roles securely
            title = str(item.data(Qt.UserRole + 1)).lower()
            author = str(item.data(Qt.UserRole + 2)).lower()
            isbn = str(item.data(Qt.UserRole)).lower()

            # Match query string against Title, Author, or ISBN string fields
            if search_query in title or search_query in author or search_query in isbn:
                item.setHidden(False)
            else:
                item.setHidden(True)

    def on_item_clicked(self, item: QListWidgetItem):
        isbn = item.data(Qt.UserRole)
        title = item.data(Qt.UserRole + 1)
        author = item.data(Qt.UserRole + 2)
        cover_bytes = item.data(Qt.UserRole + 3)
        if isbn:
            self.book_selected.emit(isbn, title, author, cover_bytes)

    def remove_item_by_isbn(self, isbn: str):
        for i in range(self.grid_widget.count()):
            item = self.grid_widget.item(i)
            if item.data(Qt.UserRole) == isbn:
                self.grid_widget.takeItem(i)
                break

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
                QMessageBox.critical(self, "Export Error", f"Could not export data: {e}")

    def clear_library_action(self):
        confirm = QMessageBox.question(
            self, "Clear Entire Library?",
            "Are you completely sure you want to purge all books from the database and UI grid view?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.filter_input.clear()
            self.grid_widget.clear()
            self.clear_library_requested.emit()
