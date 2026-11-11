"""Screen-bounded logical-pixel window sizing; independent of desktop DPI."""

from PySide6.QtCore import QRect, QSize


def window_geometry(available: QRect) -> tuple[QRect, QSize]:
    width, height = max(1, available.width() - 48), max(1, available.height() - 48)
    preferred = QSize(min(1400, width), min(900, height))
    minimum = QSize(min(1100, width), min(720, height))
    bounds = QRect(0, 0, preferred.width(), preferred.height())
    bounds.moveCenter(available.center())
    return bounds, minimum
