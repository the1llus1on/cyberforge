"""Manual baseline Qt input comparison. No database, credentials, or key logging."""

import sys

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QLineEdit, QWidget


def main() -> int:
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("CyberForge — перевірка фізичного вводу Qt")
    layout = QFormLayout(window)
    layout.addRow(QLabel(f"Qt backend: {app.platformName()}"))
    layout.addRow(QLabel("Введіть український текст фізично. Паролі не вводьте."))
    for title in ("Ім’я", "Назва групи", "Опис"):
        layout.addRow(title, QLineEdit())
    window.resize(700, 240)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
