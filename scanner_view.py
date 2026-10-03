from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QSizePolicy
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor

class ScannerView(QWidget):
    manual_isbn_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_pixmap = None
        self.laser_y = 0
        self.laser_direction = 1
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.camera_label = QLabel("Initializing Video Feed...")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px;")

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

        self.status_label = QLabel("Center an ISBN barcode to log a book")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 3px;")
        layout.addWidget(self.status_label, stretch=0)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    @Slot(QImage)
    def update_frame(self, q_img: QImage):
        """Processes and mirrors the background video thread frame matrix directly on render."""
        mirrored_img = q_img.mirrored(True, False)
        pixmap = QPixmap.fromImage(mirrored_img)
        if not self.camera_label.size().isEmpty():
            self.raw_pixmap = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.repaint_laser_overlay()

    def animate_laser(self):
        h = self.camera_label.height()
        if h > 0:
            self.laser_y += self.laser_direction * 3
            if self.laser_y >= h - 10:
                self.laser_direction = -1
            elif self.laser_y <= 10:
                self.laser_direction = 1
            self.repaint_laser_overlay()

    def repaint_laser_overlay(self):
        if self.raw_pixmap is None or self.raw_pixmap.isNull():
            return

        canvas = self.raw_pixmap.copy()
        painter = QPainter(canvas)
        pen = QPen(QColor(255, 40, 40, 220))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(0, self.laser_y, canvas.width(), self.laser_y)
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
        if style:
            self.status_label.setStyleSheet(style)
        else:
            self.status_label.setStyleSheet("font-weight: bold; font-size: 13px; padding: 3px;")
