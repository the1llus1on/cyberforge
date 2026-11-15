"""Small vector icons painted locally, without external fonts or assets."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


def icon(name: str, *, color: str = "#c2c6d1") -> QIcon:
    pixmap = QPixmap(48, 48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(
        QPen(
            QColor(color),
            1.7,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    lines = {
        "book": [
            (3, 5, 11, 7),
            (11, 7, 21, 5),
            (3, 5, 3, 19),
            (21, 5, 21, 19),
            (3, 19, 11, 21),
            (11, 21, 21, 19),
            (11, 7, 11, 21),
        ],
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
        "menu": [(4, 6, 20, 6), (4, 12, 20, 12), (4, 18, 20, 18)],
        "arrow_left": [(11, 5, 4, 12), (4, 12, 11, 19), (4, 12, 21, 12)],
        "arrow_right": [(13, 5, 20, 12), (20, 12, 13, 19), (3, 12, 20, 12)],
        "close": [(6, 6, 18, 18), (18, 6, 6, 18)],
        "mail": [
            (3, 5, 21, 5),
            (21, 5, 21, 19),
            (21, 19, 3, 19),
            (3, 19, 3, 5),
            (3, 6, 12, 13),
            (12, 13, 21, 6),
        ],
        "inbox": [
            (3, 4, 21, 4),
            (21, 4, 21, 20),
            (21, 20, 3, 20),
            (3, 20, 3, 4),
            (3, 13, 8, 13),
            (8, 13, 10, 16),
            (10, 16, 14, 16),
            (14, 16, 16, 13),
            (16, 13, 21, 13),
        ],
        "archive": [
            (3, 4, 21, 4),
            (21, 4, 21, 8),
            (21, 8, 3, 8),
            (3, 8, 3, 4),
            (4, 8, 4, 20),
            (4, 20, 20, 20),
            (20, 20, 20, 8),
            (9, 12, 15, 12),
        ],
        "trash": [
            (4, 6, 20, 6),
            (9, 3, 15, 3),
            (6, 6, 7, 21),
            (7, 21, 17, 21),
            (17, 21, 18, 6),
            (10, 10, 10, 17),
            (14, 10, 14, 17),
        ],
        "clock": [(12, 6, 12, 12), (12, 12, 16, 14)],
        "search": [(16, 16, 21, 21)],
        "compose": [
            (4, 16, 4, 21),
            (4, 21, 9, 20),
            (9, 20, 21, 8),
            (21, 8, 17, 4),
            (17, 4, 4, 16),
            (14, 7, 18, 11),
        ],
        "draft": [
            (5, 3, 15, 3),
            (15, 3, 20, 8),
            (20, 8, 20, 21),
            (20, 21, 5, 21),
            (5, 21, 5, 3),
            (15, 3, 15, 8),
            (15, 8, 20, 8),
        ],
        "send": [
            (3, 3, 22, 12),
            (22, 12, 3, 21),
            (3, 21, 7, 12),
            (7, 12, 3, 3),
            (7, 12, 22, 12),
        ],
        "spam": [(12, 7, 12, 13), (12, 17, 12, 17.2)],
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
    elif name == "search":
        painter.drawEllipse(QPointF(10, 10), 6, 6)
    elif name == "clock":
        painter.drawEllipse(QPointF(12, 12), 9, 9)
    elif name in ("star", "spam"):
        points = (
            [
                (12, 3),
                (15, 9),
                (21, 10),
                (16, 14),
                (18, 21),
                (12, 17),
                (6, 21),
                (8, 14),
                (3, 10),
                (9, 9),
            ]
            if name == "star"
            else [
                (7, 3),
                (17, 3),
                (21, 7),
                (21, 17),
                (17, 21),
                (7, 21),
                (3, 17),
                (3, 7),
            ]
        )
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
    elif name == "checkbox":
        painter.drawRoundedRect(4, 4, 16, 16, 1, 1)
    elif name == "more":
        painter.setBrush(QColor(color))
        for y in (5, 12, 19):
            painter.drawEllipse(QPointF(12, y), 0.8, 0.8)
    elif name == "refresh":
        painter.drawArc(4, 4, 16, 16, 45 * 16, 300 * 16)
        painter.drawLine(19, 4, 19, 10)
        painter.drawLine(19, 10, 13, 10)
    elif name in ("reply", "mail_forward"):
        if name == "mail_forward":
            painter.translate(24, 0)
            painter.scale(-1, 1)
        path = QPainterPath(QPointF(20, 19))
        path.cubicTo(20, 10, 14, 8, 5, 10)
        painter.drawPath(path)
        painter.drawLine(5, 10, 11, 4)
        painter.drawLine(5, 10, 11, 16)
    painter.end()
    return QIcon(pixmap)
