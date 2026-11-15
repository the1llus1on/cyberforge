"""Exact owner-observed WSLg Ukrainian shortcut repair; no text translation."""

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit

# Physical evidence supplied by the owner; these scans are NOT portable.
OBSERVED = {
    (0x421, 0x36): "copy",
    (0x41C, 0x37): "paste",
    (0x427, 0x35): "cut",
    (0x424, 0x26): "selectAll",
}


def affected_environment() -> bool:
    return (
        QApplication.platformName() == "wayland"
        and Path("/mnt/wslg/versions.txt").is_file()
    )


def correction(event, *, affected: bool) -> str | None:
    if not affected or event.modifiers() != Qt.KeyboardModifier.ControlModifier:
        return None
    if any(
        event.matches(key)
        for key in (
            QKeySequence.StandardKey.Copy,
            QKeySequence.StandardKey.Paste,
            QKeySequence.StandardKey.Cut,
            QKeySequence.StandardKey.SelectAll,
        )
    ):
        return None
    return OBSERVED.get((event.key(), event.nativeScanCode()))


class ClipboardShortcuts(QObject):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window = window

    def bind(self, app: QApplication) -> None:
        # A Python application-wide event filter wraps every Chromium internal
        # QObject, including objects being destroyed. Filter native editors only.
        app.focusChanged.connect(self._focus_changed)
        self._focus_changed(None, app.focusWidget())

    def _focus_changed(self, old, current) -> None:
        if isinstance(current, (QLineEdit, QPlainTextEdit, QTextEdit)) and (
            self.window.isAncestorOf(current)
        ):
            current.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() not in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride)
            or not isinstance(watched, (QLineEdit, QPlainTextEdit, QTextEdit))
            or not self.window.isAncestorOf(watched)
            or not watched.isEnabled()
        ):
            return False
        action = correction(event, affected=affected_environment())
        if action is None:
            return False
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()  # Prevent another shortcut claiming this editing action.
            return True
        password = (
            isinstance(watched, QLineEdit)
            and watched.echoMode() != QLineEdit.EchoMode.Normal
        )
        forbidden = (password and action in ("copy", "cut")) or (
            watched.isReadOnly() and action in ("cut", "paste")
        )
        if not forbidden:
            getattr(watched, action)()  # Native operations preserve undo/validation.
        event.accept()
        return True  # Consume once; never deliver a second synthetic key event.
