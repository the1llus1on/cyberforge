"""Native progressive disclosure and responsive preparation layouts."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class PreparationStack(QStackedWidget):
    """Hidden previews must not impose their minimum geometry on other steps."""

    def minimumSizeHint(self) -> QSize:
        return QSize(320, 180)

    def sizeHint(self) -> QSize:
        return QSize(820, 420)


class Disclosure(QWidget):
    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.toggle = QPushButton("▸ " + title)
        self.toggle.setCheckable(True)
        self.toggle.setAccessibleName(title)
        self.content = content
        layout.addWidget(self.toggle)
        layout.addWidget(content)
        content.hide()

        def expand(checked):
            content.setVisible(checked)
            self.toggle.setText(("▾ " if checked else "▸ ") + title)
            self.toggle.setAccessibleDescription(
                "Розгорнуто" if checked else "Згорнуто"
            )

        self.toggle.toggled.connect(expand)


class MaterialCards(QWidget):
    def __init__(self, cards: tuple[QFrame, QFrame]):
        super().__init__()
        self.cards_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        for card in cards:
            self.cards_layout.addWidget(card, 1)

    def resizeEvent(self, event):
        self.cards_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if event.size().width() < 650
            else QBoxLayout.Direction.LeftToRight
        )
        super().resizeEvent(event)


def preparation_scroll(layout) -> QFrame:
    """Each step owns one scroll surface; previews use the full content area."""
    from PySide6.QtWidgets import QScrollArea

    body = QWidget()
    body.setLayout(layout)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(body)
    return scroll
