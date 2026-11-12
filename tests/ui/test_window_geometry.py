"""Logical screen bounds and usable fallback when compositor ignores minimum."""

import runpy
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from cyberforge.ui.window_geometry import window_geometry


def test_initial_frame_stays_in_available_screen(qtbot, tmp_path):
    from cyberforge.application.accounts import AccountService
    from cyberforge.persistence.database import Database
    from cyberforge.ui.shell import MainWindow

    database = Database(tmp_path / "frame.sqlite3")
    try:
        database.upgrade()
        window = MainWindow(AccountService(database))
        qtbot.addWidget(window)
        window.show()
        qtbot.wait(30)
        assert window.screen().availableGeometry().contains(window.frameGeometry())
        if sys.platform == "win32" and QApplication.platformName() == "windows":
            probe = runpy.run_path(
                str(Path(__file__).parents[2] / "tools/window_probe.py")
            )
            width, height = probe["native_minimum"](window)
            assert width >= window.minimumWidth() * window.devicePixelRatioF()
            assert height >= window.minimumHeight() * window.devicePixelRatioF()
        window.resize(window.minimumWidth() + 20, window.minimumHeight() + 10)
        qtbot.wait(20)
        assert window.width() == window.minimumWidth() + 20
        assert window.height() == window.minimumHeight() + 10
        window.close()
    finally:
        database.close()


@pytest.mark.parametrize(
    "bounds",
    [
        QRect(0, 0, 1920, 1080),
        QRect(-1280, 0, 1280, 800),
        QRect(0, 0, 800, 600),
        QRect(0, 0, 640, 480),
    ],
)
def test_screen_sizing(bounds):
    preferred, minimum = window_geometry(bounds)
    assert bounds.contains(preferred)
    assert preferred.width() >= minimum.width()
    assert preferred.height() >= minimum.height()
    if bounds.width() >= 1448 and bounds.height() >= 948:
        assert preferred.size().toTuple() == (1400, 900)
        assert minimum.toTuple() == (1100, 720)
