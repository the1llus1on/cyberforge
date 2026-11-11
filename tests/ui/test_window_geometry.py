"""Logical screen bounds and usable fallback when compositor ignores minimum."""

import pytest
from PySide6.QtCore import QRect

from cyberforge.ui.window_geometry import window_geometry


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
