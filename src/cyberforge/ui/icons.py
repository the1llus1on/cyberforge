"""Small vector icons painted locally, without external fonts or assets."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def icon(name: str) -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#c2c6d1"), 1.7))
    lines = {
        "plus": [(5, 12, 19, 12), (12, 5, 12, 19)],
        "chart": [
            (5, 4, 5, 20),
            (5, 20, 21, 20),
            (10, 15, 10, 10),
            (14, 15, 14, 6),
            (18, 15, 18, 3),
        ],
        "back": [(16, 6, 10, 12), (10, 12, 16, 18)],
        "forward": [(9, 6, 15, 12), (15, 12, 9, 18)],
        "home": [
            (3, 11, 12, 3),
            (12, 3, 21, 11),
            (6, 10, 6, 21),
            (6, 21, 18, 21),
            (18, 21, 18, 10),
        ],
        "settings": [
            (12, 2, 12, 5),
            (12, 19, 12, 22),
            (2, 12, 5, 12),
            (19, 12, 22, 12),
            (5, 5, 7, 7),
            (17, 17, 19, 19),
            (5, 19, 7, 17),
            (17, 7, 19, 5),
        ],
    }
    for x1, y1, x2, y2 in lines.get(name, []):
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    if name == "settings":
        painter.drawEllipse(QPointF(12, 12), 6, 6)
        painter.drawEllipse(QPointF(12, 12), 2, 2)
    elif name == "profile":
        painter.drawEllipse(QPointF(12, 7), 4, 4)
        painter.drawArc(4, 13, 16, 15, 0, 180 * 16)
    painter.end()
    return QIcon(pixmap)
