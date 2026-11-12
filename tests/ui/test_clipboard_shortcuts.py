"""Observed physical shortcut mapping, exact scope, and native edit protections."""

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from cyberforge.ui import clipboard_shortcuts as shortcuts

CTRL = Qt.KeyboardModifier.ControlModifier


def event(key=0x41C, scan=0x37, modifiers=CTRL, kind=QEvent.Type.KeyPress):
    return QKeyEvent(kind, key, modifiers, scan, 0, 0)


@pytest.mark.parametrize("pair,action", list(shortcuts.OBSERVED.items()))
def test_confirmed_mapping(qapp, pair, action):
    assert shortcuts.correction(event(*pair), affected=True) == action
    assert shortcuts.correction(event(*pair), affected=False) is None


@pytest.mark.parametrize(
    "key,scan,modifiers",
    [
        (0x56, 0x37, CTRL),
        (0x41C, 0x38, CTRL),
        (0x41D, 0x37, CTRL),
        (0x41C, 0x37, Qt.KeyboardModifier.NoModifier),
        (0x41C, 0x37, CTRL | Qt.KeyboardModifier.AltModifier),
        (0x41C, 0x37, CTRL | Qt.KeyboardModifier.ShiftModifier),
        (0x41C, 0x37, CTRL | Qt.KeyboardModifier.GroupSwitchModifier),
        (
            Qt.Key.Key_Insert,
            0x5A,
            Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.KeypadModifier,
        ),
    ],
)
def test_non_matching_events_passthrough(qapp, key, scan, modifiers):
    assert shortcuts.correction(event(key, scan, modifiers), affected=True) is None


@pytest.mark.parametrize("widget_class", [QLineEdit, QPlainTextEdit, QTextEdit])
def test_native_editing_single_execution(qtbot, monkeypatch, widget_class):
    monkeypatch.setattr(shortcuts, "affected_environment", lambda: True)
    window = QWidget()
    field = widget_class(window)
    qtbot.addWidget(window)
    handler = shortcuts.ClipboardShortcuts(window)
    app = QApplication.instance()
    app.installEventFilter(handler)
    clipboard = app.clipboard()
    previous = clipboard.text()
    try:
        clipboard.setText("Київ")
        spy = QSignalSpy(field.textChanged)
        app.sendEvent(field, event(kind=QEvent.Type.ShortcutOverride))
        assert spy.count() == 0
        app.sendEvent(field, event())
        text = field.text if isinstance(field, QLineEdit) else field.toPlainText
        assert text() == "Київ"
        assert spy.count() == 1
        app.sendEvent(field, event(0x424, 0x26))
        app.sendEvent(field, event(0x421, 0x36))
        assert clipboard.text() == "Київ"
        app.sendEvent(field, event(0x427, 0x35))
        assert text() == ""
        assert clipboard.text() == "Київ"
        # Normal English and Shift+Insert remain Qt's responsibility.
        qtbot.keyClick(field, Qt.Key.Key_V, CTRL)
        assert text() == "Київ"
        qtbot.keyClick(field, Qt.Key.Key_A, CTRL)
        qtbot.keyClick(field, Qt.Key.Key_C, CTRL)
        assert clipboard.text() == "Київ"
        qtbot.keyClick(field, Qt.Key.Key_X, CTRL)
        assert text() == ""
        field.clear()
        qtbot.keyClick(field, Qt.Key.Key_Insert, Qt.KeyboardModifier.ShiftModifier)
        assert text() == "Київ"
    finally:
        app.removeEventFilter(handler)
        clipboard.setText(previous)


@pytest.mark.parametrize(
    "echo",
    [
        QLineEdit.EchoMode.Password,
        QLineEdit.EchoMode.PasswordEchoOnEdit,
        QLineEdit.EchoMode.NoEcho,
    ],
)
def test_password_protection_and_scope(qtbot, monkeypatch, echo):
    monkeypatch.setattr(shortcuts, "affected_environment", lambda: True)
    window, unrelated = QWidget(), QLineEdit()
    qtbot.addWidget(window)
    qtbot.addWidget(unrelated)
    field = QLineEdit(window)
    field.setText("private")
    field.setEchoMode(echo)
    field.selectAll()
    handler = shortcuts.ClipboardShortcuts(window)
    clipboard = QApplication.clipboard()
    previous = clipboard.text()
    try:
        clipboard.setText("sentinel")
        for key, scan in ((0x421, 0x36), (0x427, 0x35)):
            assert handler.eventFilter(field, event(key, scan))
            assert clipboard.text() == "sentinel"
            assert field.text() == "private"
        assert not handler.eventFilter(unrelated, event())
        field.setReadOnly(True)
        handler.eventFilter(field, event())
        assert field.text() == "private"
        assert not handler.eventFilter(field, QEvent(QEvent.Type.InputMethod))
        field.setReadOnly(False)
        handler.eventFilter(field, event(0x424, 0x26))
        handler.eventFilter(field, event())
        assert field.text() == "sentinel"
    finally:
        clipboard.setText(previous)


@pytest.mark.parametrize(
    "backend,present,expected",
    [
        ("windows", True, False),
        ("xcb", True, False),
        ("wayland", False, False),
        ("wayland", True, True),
    ],
)
def test_environment_detection(monkeypatch, qapp, backend, present, expected):
    monkeypatch.setattr(shortcuts.QApplication, "platformName", lambda: backend)
    monkeypatch.setattr(shortcuts.Path, "is_file", lambda path: present)
    assert shortcuts.affected_environment() == expected
