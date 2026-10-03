import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from ui import MainWindow

def apply_forced_dark_theme(app: QApplication):
    """Overrides default system look-and-feel to enforce a uniform dark style."""
    app.setStyle('Fusion')

    dark_palette = QPalette()
    dark_gray = QColor(30, 30, 46)
    darker_gray = QColor(24, 24, 37)
    charcoal = QColor(17, 17, 27)
    light_gray = QColor(205, 214, 244)
    mid_gray = QColor(166, 173, 200)
    accent_purple = QColor(203, 166, 247)

    dark_palette.setColor(QPalette.Window, dark_gray)
    dark_palette.setColor(QPalette.WindowText, light_gray)
    dark_palette.setColor(QPalette.Base, charcoal)
    dark_palette.setColor(QPalette.AlternateBase, darker_gray)
    dark_palette.setColor(QPalette.ToolTipBase, light_gray)
    dark_palette.setColor(QPalette.ToolTipText, dark_gray)
    dark_palette.setColor(QPalette.Text, light_gray)
    dark_palette.setColor(QPalette.Button, darker_gray)
    dark_palette.setColor(QPalette.ButtonText, light_gray)
    dark_palette.setColor(QPalette.BrightText, accent_purple)
    dark_palette.setColor(QPalette.Link, accent_purple)

    dark_palette.setColor(QPalette.Highlight, accent_purple)
    dark_palette.setColor(QPalette.HighlightedText, charcoal)

    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, mid_gray)
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, mid_gray)
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, mid_gray)

    app.setPalette(dark_palette)

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.argv += ["-platform", "windows:darkmode=2"]

    app = QApplication(sys.argv)
    apply_forced_dark_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
