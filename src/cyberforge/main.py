"""Desktop application entry point."""

import argparse
import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Start the guest shell; smoke mode exits through the Qt event loop."""
    parser = argparse.ArgumentParser(description="CyberForge — навчальна платформа")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Перевірити запуск і закрити вікно"
    )
    args = parser.parse_args(argv)

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from cyberforge.ui.shell import MainWindow
    from cyberforge.ui.theme import apply_theme

    app = QApplication([sys.argv[0]])
    app.setApplicationName("CyberForge")
    app.setOrganizationName("CyberForge")
    apply_theme(app)
    window = MainWindow()
    window.show()
    if args.smoke_test:
        QTimer.singleShot(500, window.close)
    return app.exec()
