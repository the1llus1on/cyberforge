"""Read-only JSON source of the native-widget Email preview."""

import re

from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.ui.pages import label


class JsonHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text: str) -> None:
        for match in re.finditer(
            r'"(?:[^"\\]|\\.)*"|\b(?:true|false|null|\d+)\b', text
        ):
            color = (
                "#c4afff" if text[match.end() :].lstrip().startswith(":") else "#9cdbb5"
            )
            style = QTextCharFormat()
            style.setForeground(QColor(color))
            self.setFormat(match.start(), match.end() - match.start(), style)


class EmailSourceDialog(QDialog):
    def __init__(self, draft: EmailDraftV2, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Переглянути код · JSON / EmailDraftV2")
        self.resize(820, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(label("JSON · EmailDraftV2 · лише читання", "heading"))
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setTabChangesFocus(True)
        self.source.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.source.setAccessibleName("Структурований EmailDraftV2, JSON")
        self.source.setPlainText(draft.model_dump_json(indent=2))
        self.highlighter = JsonHighlighter(self.source.document())
        layout.addWidget(self.source)
        actions = QHBoxLayout()
        self.copy_button = QPushButton("Копіювати JSON")
        self.copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.source.toPlainText())
        )
        actions.addWidget(self.copy_button)
        close = QPushButton("Закрити")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
