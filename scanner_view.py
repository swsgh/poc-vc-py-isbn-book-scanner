from PySide6.QtCore import Qt, Signal, Slot, QRect
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QSizePolicy
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QRegion, QPalette

class ScannerView(QWidget):
    manual_isbn_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_pixmap = None
        self._custom_status_style = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.camera_label = QLabel("Initializing Video Feed...")
        self.camera_label.setAlignment(Qt.AlignCenter)

        # Enforce highly restrictive layout compression metrics
        self.camera_label.setMinimumHeight(240)
        self.camera_label.setMaximumHeight(260)
        layout.addWidget(self.camera_label, stretch=0)

        manual_layout = QHBoxLayout()
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Type an ISBN code manually (e.g. 9781449392178)...")
        self.manual_input.returnPressed.connect(self.submit_manual_isbn)
        manual_layout.addWidget(self.manual_input)

        self.manual_btn = QPushButton("🔍 Lookup")
        self.manual_btn.setObjectName("manualBtn")
        self.manual_btn.clicked.connect(self.submit_manual_isbn)
        manual_layout.addWidget(self.manual_btn)
        layout.addLayout(manual_layout)

        self.status_label = QLabel("Center an ISBN barcode to add a book")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.apply_palette_styles()
        layout.addWidget(self.status_label, stretch=0)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def apply_palette_styles(self, palette=None):
        palette = palette or self.palette()
        border_color = palette.color(QPalette.Mid).name()
        text_color = palette.color(QPalette.WindowText).name()
        self.camera_label.setStyleSheet(
            f"border: 1px solid {border_color}; border-radius: 6px;"
        )
        self.status_label.setStyleSheet(
            self._custom_status_style
            or f"font-weight: bold; font-size: 13px; padding: 3px; color: {text_color};"
        )

    @Slot(QImage)
    def update_frame(self, q_img: QImage):
        """Processes and mirrors the background video thread frame matrix directly on render."""
        mirrored_img = q_img.mirrored(True, False)
        pixmap = QPixmap.fromImage(mirrored_img)
        if not self.camera_label.size().isEmpty():
            self.raw_pixmap = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.repaint_scan_overlay()

    def repaint_scan_overlay(self):
        if self.raw_pixmap is None or self.raw_pixmap.isNull():
            return

        canvas = self.raw_pixmap.copy()
        painter = QPainter(canvas)
        box_width = int(canvas.width() * 0.7)
        box_height = int(canvas.height() * 0.25)
        x = (canvas.width() - box_width) // 2
        y = (canvas.height() - box_height) // 2
        scan_zone = QRect(x, y, box_width, box_height)

        outside_zone = QRegion(canvas.rect()).subtracted(QRegion(scan_zone))
        painter.setClipRegion(outside_zone)
        painter.fillRect(canvas.rect(), QColor(0, 0, 0, 100))
        painter.setClipping(False)

        corner_length = min(20, box_width // 4, box_height // 3)
        painter.setPen(QPen(QColor("#27ae60"), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(x, y, x + corner_length, y)
        painter.drawLine(x, y, x, y + corner_length)
        painter.drawLine(x + box_width, y, x + box_width - corner_length, y)
        painter.drawLine(x + box_width, y, x + box_width, y + corner_length)
        painter.drawLine(x, y + box_height, x + corner_length, y + box_height)
        painter.drawLine(x, y + box_height, x, y + box_height - corner_length)
        painter.drawLine(x + box_width, y + box_height, x + box_width - corner_length, y + box_height)
        painter.drawLine(x + box_width, y + box_height, x + box_width, y + box_height - corner_length)

        painter.setPen(QPen(QColor("#e74c3c"), 2, Qt.DashLine))
        center_y = y + box_height // 2
        painter.drawLine(x + 5, center_y, x + box_width - 5, center_y)
        painter.end()
        self.camera_label.setPixmap(canvas)

    def submit_manual_isbn(self):
        text = self.manual_input.text().strip().replace("-", "")
        if not text:
            return
        if text.isdigit() and len(text) in (10, 13):
            self.manual_input.clear()
            self.manual_isbn_submitted.emit(text)
        else:
            QMessageBox.warning(self, "Invalid Input", "ISBN must be a string of 10 or 13 numbers.")

    def set_status(self, text: str, style: str = None):
        self.status_label.setText(text)
        self._custom_status_style = style
        self.apply_palette_styles()
