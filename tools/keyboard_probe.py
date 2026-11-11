"""Opt-in shortcut metadata probe. Never records text or clipboard contents."""

import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)


def shortcut_metadata(event, backend: str) -> str | None:
    """Report control shortcuts only; never call event.text() or read clipboard."""
    modifiers = event.modifiers()
    if modifiers & (
        Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.GroupSwitchModifier
    ):
        return None
    control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
    insert = event.key() == Qt.Key.Key_Insert and bool(
        modifiers & Qt.KeyboardModifier.ShiftModifier
    )
    if not control and not insert:
        return None
    matches = [
        name
        for name in ("Copy", "Paste", "Cut", "SelectAll")
        if event.matches(getattr(QKeySequence.StandardKey, name))
    ]
    return (
        f"backend={backend} key=0x{event.key():X} modifiers=0x{modifiers.value:X} "
        f"scan=0x{event.nativeScanCode():X} virtual=0x{event.nativeVirtualKey():X} "
        f"standard={','.join(matches) or '-'}"
    )


class ShortcutProbe(QObject):
    def __init__(self, fields, report, parent) -> None:
        super().__init__(parent)
        self.fields, self.report = fields, report

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in self.fields
            and isinstance(watched, QLineEdit)
            and watched.echoMode() == QLineEdit.EchoMode.Normal
            and event.type() == QEvent.Type.KeyPress
        ):
            metadata = shortcut_metadata(event, QApplication.platformName())
            if metadata:
                self.report.appendPlainText(metadata)
        return False  # Observe only; preserve Qt editing and all input behavior.


def main() -> int:
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("CyberForge — перевірка фізичного вводу Qt")
    layout = QFormLayout(window)
    layout.addRow(QLabel(f"Qt backend: {app.platformName()}"))
    paste_keys = QKeySequence.keyBindings(QKeySequence.StandardKey.Paste)
    layout.addRow(
        QLabel("Qt Paste: " + "; ".join(key.toString() for key in paste_keys))
    )
    layout.addRow(
        QLabel(
            "Лише тестовий текст. Паролі не вводьте. "
            "Журнал показує тільки shortcut-метадані."
        )
    )
    fields = []
    for title in ("Ім’я", "Назва групи", "Опис"):
        field = QLineEdit()
        fields.append(field)
        layout.addRow(title, field)
    report = QPlainTextEdit()
    report.setReadOnly(True)
    report.setMaximumBlockCount(24)
    layout.addRow("Події Ctrl / Shift+Insert", report)
    probe = ShortcutProbe(fields, report, window)
    app.installEventFilter(probe)
    window.resize(950, 450)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
