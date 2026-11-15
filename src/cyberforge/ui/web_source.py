"""Read-only actual renderer inputs and current canonical JSON."""

import re

from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from cyberforge.ui.pages import label


class SourceHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        for match in re.finditer(
            r'<[^>]+>|"(?:[^"\\]|\\.)*"|[\w-]+(?=\s*:)|#[0-9a-fA-F]{3,8}', text
        ):
            style = QTextCharFormat()
            style.setForeground(
                QColor("#a6d9c0" if match.group().startswith('"') else "#baa4ef")
            )
            self.setFormat(match.start(), match.end() - match.start(), style)


class WebSourceDialog(QDialog):
    def __init__(self, draft, rendered, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Код навчального сайту")
        self.resize(840, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(
            label("Фактичні HTML/CSS preview та поточний canonical JSON. Лише читання.")
        )
        self.tabs = QTabWidget()
        self.sources = {}
        self.highlighters = []
        for name, value in (
            ("HTML", rendered.html),
            ("CSS", rendered.css),
            ("JSON", draft.model_dump_json(indent=2)),
        ):
            field = QPlainTextEdit(value)
            field.setReadOnly(True)
            field.setTabChangesFocus(True)
            field.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            field.setAccessibleName(name)
            self.sources[name] = field
            self.highlighters.append(SourceHighlighter(field.document()))
            self.tabs.addTab(field, name)
        layout.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        self.copy_button = QPushButton("Копіювати")
        self.copy_button.clicked.connect(self.copy_current)
        row.addWidget(self.copy_button)
        close = QPushButton("Закрити")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)

    def copy_current(self):
        QApplication.clipboard().setText(self.tabs.currentWidget().toPlainText())

    def clear_sources(self):
        for source in self.sources.values():
            source.clear()
