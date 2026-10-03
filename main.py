import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from ui import MainWindow

def apply_forced_dark_theme(app):
    """Overrides system styling configurations to enforce a clean, dark Fusion theme."""
    # 1. Choose the cross-platform 'Fusion' theme engine to handle uniform dark formatting
    app.setStyle('Fusion')

    # 2. Re-map the master application color palette explicitly
    dark_palette = QPalette()

    # Palette Color Definitions
    dark_gray = QColor(30, 30, 46)
    darker_gray = QColor(24, 24, 37)
    charcoal = QColor(17, 17, 27)
    light_gray = QColor(205, 214, 244)
    mid_gray = QColor(166, 173, 200)
    accent_purple = QColor(203, 166, 247)

    # Map color definitions cleanly to core Qt functional states
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

    # System highlights and selections
    dark_palette.setColor(QPalette.Highlight, accent_purple)
    dark_palette.setColor(QPalette.HighlightedText, charcoal)

    # Deactivated or disabled text layers
    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, mid_gray)
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, mid_gray)
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, mid_gray)

    # Inject the palette setup back to application scope
    app.setPalette(dark_palette)

if __name__ == "__main__":
    # Force platform hooks on Windows environments if preferred
    if sys.platform == "win32":
        sys.argv += ["-platform", "windows:darkmode=2"]

    app = QApplication(sys.argv)

    # Enforce palette before showing the main window layout shell
    apply_forced_dark_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
