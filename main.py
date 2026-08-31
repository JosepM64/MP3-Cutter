from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root on path when running as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mp3_cutter.ui.main_window import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


def main() -> None:
    # High DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("MP3 Cutter")
    app.setOrganizationName("JM")
    app.setStyle("Fusion")

    # Dark palette
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#121212"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#eeeeee"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#252525"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2a2a2a"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#eeeeee"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#eeeeee"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#2a2a2a"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#eeeeee"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ff3d00"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#0288d1"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    app.setPalette(pal)

    w = MainWindow()
    # Optional icon if exists
    icon_path = ROOT / "resources" / "icon.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
        w.setWindowIcon(QIcon(str(icon_path)))

    # Allow opening file via argv
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.is_file():
            w.load_file(p)

    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
