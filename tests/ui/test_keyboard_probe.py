"""Probe metadata contains no text and never changes application editing."""

import runpy
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit

PROBE = runpy.run_path(str(Path(__file__).parents[2] / "tools/keyboard_probe.py"))


def test_probe_metadata_only(qapp):
    metadata = PROBE["shortcut_metadata"]
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_V,
        Qt.KeyboardModifier.ControlModifier,
        "DO-NOT-REPORT",
    )
    report = metadata(event, "wayland")
    assert "key=0x56" in report and "Paste" in report
    assert "DO-NOT-REPORT" not in report
    assert (
        metadata(
            QKeyEvent(QEvent.Type.KeyPress, 0x41C, Qt.KeyboardModifier.NoModifier, "м"),
            "wayland",
        )
        is None
    )
    assert (
        metadata(
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_V,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
                "private",
            ),
            "wayland",
        )
        is None
    )


def test_probe_does_not_observe_passwords(qtbot):
    field, report = QLineEdit(), QPlainTextEdit()
    qtbot.addWidget(field)
    qtbot.addWidget(report)
    field.setEchoMode(QLineEdit.EchoMode.Password)
    probe = PROBE["ShortcutProbe"]([field], report, field)
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_V,
        Qt.KeyboardModifier.ControlModifier,
        "not-recorded",
    )
    assert not probe.eventFilter(field, event)
    assert not report.toPlainText()


@pytest.mark.parametrize("method", ["standard", "shift_insert", "paste_action"])
def test_qt_standard_unicode_paste(qtbot, method):
    field = QLineEdit()
    qtbot.addWidget(field)
    field.show()
    field.setFocus()
    clipboard = QApplication.clipboard()
    previous = clipboard.text()
    try:
        clipboard.setText("Україна Київ")
        if method == "standard":
            qtbot.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        elif method == "shift_insert":
            qtbot.keyClick(field, Qt.Key.Key_Insert, Qt.KeyboardModifier.ShiftModifier)
        else:
            field.paste()
        assert field.text() == "Україна Київ"
    finally:
        clipboard.setText(previous)


def test_probe_preserves_editing_and_password_copy(qtbot):
    field, report = QLineEdit(), QPlainTextEdit()
    qtbot.addWidget(field)
    qtbot.addWidget(report)
    probe = PROBE["ShortcutProbe"]([field], report, field)
    app = QApplication.instance()
    app.installEventFilter(probe)
    clipboard = QApplication.clipboard()
    previous = clipboard.text()
    try:
        field.show()
        field.setFocus()
        field.setText("Тест")
        qtbot.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        assert field.selectedText() == "Тест"
        qtbot.keyClick(field, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert clipboard.text() == "Тест"
        qtbot.keyClick(field, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
        assert not field.text()
        qtbot.keyClick(field, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        assert field.text() == "Тест"
        assert "Тест" not in report.toPlainText()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.selectAll()
        clipboard.setText("sentinel")
        qtbot.keyClick(field, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert clipboard.text() == "sentinel"
    finally:
        app.removeEventFilter(probe)
        clipboard.setText(previous)
