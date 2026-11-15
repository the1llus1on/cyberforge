"""Read-only inspection of the actual current canonical JSON draft."""

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
        self.setWindowTitle("Структура електронного листа (JSON)")
        self.resize(820, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Структура електронного листа (JSON)", "heading"))
        self.explanation = label(
            "JSON — структуроване представлення навчального листа, яке використовує "
            "CyberForge для перевірки, збереження та "
            "відновлення матеріалу. Лише читання."
        )
        layout.addWidget(self.explanation)
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setTabChangesFocus(True)
        self.source.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.source.setAccessibleName("Структурований EmailDraftV2, JSON")
        self.source.setPlainText(draft.model_dump_json(indent=2))
        self.highlighter = JsonHighlighter(self.source.document())
        layout.addWidget(self.source, 1)
        actions = QHBoxLayout()
        self.copy_button = QPushButton("Копіювати JSON")
        self.copy_button.clicked.connect(self.copy_current)
        actions.addWidget(self.copy_button)
        close = QPushButton("Закрити")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)

    def copy_current(self) -> None:
        QApplication.clipboard().setText(self.source.toPlainText())

    def clear_sources(self) -> None:
        self.source.clear()
