"""Native progressive disclosure and responsive preparation layouts."""

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QLabel,
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


class CheckLabel(QLabel):
    """Wrapping text with the same click target behavior as a native checkbox."""

    def __init__(self, text, checkbox):
        super().__init__(text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setBuddy(checkbox)

    def mouseReleaseEvent(self, event):
        checkbox = self.buddy()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and checkbox is not None
            and checkbox.isEnabled()
        ):
            checkbox.setFocus()
            checkbox.click()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class MaterialCards(QWidget):
    def __init__(self, cards: tuple[QFrame, QFrame]):
        super().__init__()
        self.cards = cards
        self.viewport = None
        self.cards_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        for card in cards:
            self.cards_layout.addWidget(card, 1)

    def follow_viewport(self, viewport: QWidget) -> None:
        self.viewport = viewport
        viewport.installEventFilter(self)
        self._adapt(viewport.width())

    def _adapt(self, width: int) -> None:
        # A wide native card minimum can prevent this widget from shrinking.
        # Choose direction from the viewport, independently of that minimum.
        parent_layout = self.parentWidget().layout() if self.parentWidget() else None
        if parent_layout:
            margins = parent_layout.contentsMargins()
            width -= margins.left() + margins.right()
        required = (
            sum(
                max(card.minimumWidth(), card.minimumSizeHint().width())
                for card in self.cards
            )
            + self.cards_layout.spacing()
        )
        direction = (
            QBoxLayout.Direction.TopToBottom
            if width < max(650, required)
            else QBoxLayout.Direction.LeftToRight
        )
        if self.cards_layout.direction() != direction:
            self.cards_layout.setDirection(direction)
            self.updateGeometry()

    def eventFilter(self, watched, event):
        if watched is self.viewport and event.type() == QEvent.Type.Resize:
            self._adapt(event.size().width())
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        self._adapt(self.viewport.width() if self.viewport else event.size().width())
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
