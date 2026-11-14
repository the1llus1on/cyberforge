"""Developer-controlled native document formatting; artifact strings stay text."""

from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextFrameFormat,
)
from PySide6.QtWidgets import QSizePolicy, QTextEdit

from cyberforge.agents.contracts import MessageV1


class MessageBody(QTextEdit):
    """Readable paragraphs and an inert resource card, without parsing HTML."""

    def __init__(self) -> None:
        super().__init__()
        self._main_message = False
        self.setObjectName("mailBody")
        self.setAccessibleName("Вміст синтетичного листа · лише читання")
        self.setReadOnly(True)
        self.setAcceptRichText(False)
        self.setAcceptDrops(False)
        self.setUndoRedoEnabled(False)
        self.setTabChangesFocus(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setMinimumSize(0, 65)
        # Native text size hints vary by platform. Neither document width nor
        # its preferred height may enlarge the surrounding constructor page.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.document().setDocumentMargin(6)

    def loadResource(self, resource_type, name):
        # Defense in depth: even future document changes cannot load resources.
        return None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._content_margins()

    def _content_margins(self) -> None:
        margin = (
            max(6, (self.viewport().width() - 640) // 2) if self._main_message else 6
        )
        frame = self.document().rootFrame()
        style = frame.frameFormat()
        if style.leftMargin() != margin or style.rightMargin() != margin:
            style.setLeftMargin(margin)
            style.setRightMargin(margin)
            frame.setFrameFormat(style)

    def _style(self, size: int, color: str, *, bold: bool = False) -> QTextCharFormat:
        style = QTextCharFormat()
        font = QFont(self.font())
        font.setPixelSize(size)
        font.setBold(bold)
        style.setFont(font)
        style.setForeground(QColor(color))
        return style

    def set_message(self, message: MessageV1, resource_id: str | None) -> None:
        self.clear()
        self._main_message = resource_id is not None
        cursor = QTextCursor(self.document())
        paragraph = QTextBlockFormat()
        paragraph.setLineHeight(
            145, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
        )
        if resource_id is not None:
            header = QTextFrameFormat()
            header.setBackground(QColor("#edf3fd"))
            header.setPadding(12)
            header.setBottomMargin(12)
            frame = cursor.insertFrame(header)
            cursor.setBlockFormat(paragraph)
            cursor.insertText(
                message.sender_name, self._style(14, "#174ea6", bold=True)
            )
            cursor.setPosition(frame.lastPosition() + 1)
            cursor.setBlockFormat(paragraph)
        else:
            cursor.setBlockFormat(paragraph)
        # insertText never interprets tags, URLs, CSS or commands in model data.
        cursor.insertText(message.body_text, self._style(15, "#202124"))
        if resource_id is not None:
            information = QTextFrameFormat()
            information.setTopMargin(18)
            information.setPadding(12)
            information.setBorder(1)
            information.setBorderBrush(QColor("#e0e6ef"))
            information.setBackground(QColor("#f1f5fb"))
            cursor.insertBlock(paragraph)
            cursor.insertFrame(information)
            cursor.setBlockFormat(paragraph)
            cursor.insertText(
                "Навчальний ресурс", self._style(12, "#5f6368", bold=True)
            )
            cursor.insertBlock(paragraph)
            cursor.insertText(resource_id, self._style(13, "#3c4043"))
            action = QTextFrameFormat()
            action.setTopMargin(8)
            action.setPadding(8)
            action.setBackground(QColor("#d3e3fd"))
            cursor.insertBlock(paragraph)
            cursor.insertFrame(action)
            cursor.setBlockFormat(paragraph)
            cursor.insertText(
                "Переглянути навчальний матеріал · перехід вимкнено",
                self._style(13, "#0b57d0", bold=True),
            )
        self.setTextCursor(QTextCursor(self.document()))
        self._content_margins()
        self.verticalScrollBar().setValue(0)
