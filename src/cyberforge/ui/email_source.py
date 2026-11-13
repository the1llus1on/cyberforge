"""Canonical JSON and a separate, inert HTML projection of message content."""

import re
from html import escape

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

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.ui.email_preview import MAILBOX_ADDRESS, training_time
from cyberforge.ui.pages import label


def render_email_html(draft: EmailDraftV2, selected_index: int = 0) -> str:
    """Inspection projection only: never the source of the native Qt interface.

    Escape every artifact field, including already validated strings. No active
    links, styles, forms, scripts or external resources are emitted or executed.
    """
    messages = [draft.slots.main, *draft.slots.background]
    if not 0 <= selected_index < len(messages):
        raise ValueError("Unknown message index")
    message = messages[selected_index]
    body = "<br>\n".join(escape(line) for line in message.body_text.split("\n"))
    resource = (
        "Навчальне посилання (без переходу): " + draft.slots.internal_resource_id
        if selected_index == 0
        else "Фоновий синтетичний лист"
    )
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="uk">',
            '<head><meta charset="utf-8">',
            f"<title>{escape(message.subject)}</title></head>",
            "<body><article>",
            "<header>",
            f"<h1>{escape(message.subject)}</h1>",
            "<dl>",
            "<dt>Від</dt>",
            f"<dd>{escape(message.sender_name)} "
            f"&lt;{escape(message.sender_address)}&gt;</dd>",
            "<dt>Кому</dt>",
            f"<dd>Навчальний учасник &lt;{escape(MAILBOX_ADDRESS)}&gt;</dd>",
            "</dl>",
            f"<p>{escape(training_time(selected_index))} · навчальний час</p>",
            "</header>",
            f'<section aria-label="Текст листа"><p>{body}</p></section>',
            f"<footer><p>{escape(resource)}</p></footer>",
            "</article></body>",
            "</html>",
        )
    )


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


class HtmlHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text: str) -> None:
        for pattern, color in (
            (r"</?[^>]+>|<!doctype[^>]*>", "#b8a1ff"),
            (r'"[^"<>]*"', "#9cdbb5"),
            (r"&[a-zA-Z0-9#]+;", "#e9bf80"),
        ):
            for match in re.finditer(pattern, text):
                style = QTextCharFormat()
                style.setForeground(QColor(color))
                self.setFormat(match.start(), match.end() - match.start(), style)


class EmailSourceDialog(QDialog):
    def __init__(
        self, draft: EmailDraftV2, parent=None, *, selected_index: int = 0
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Структура / код електронного листа")
        self.resize(820, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Структура та проєкція листа · лише читання", "heading"))
        self.explanation = label(
            "JSON — канонічний EmailDraftV2, який зберігається в SQLite. "
            "HTML — локальна проєкція вмісту вибраного листа для перевірки. "
            "AI не повертає цей HTML; нативний поштовий макет Qt його не використовує."
        )
        layout.addWidget(self.explanation)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setTabChangesFocus(True)
        self.source.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.source.setAccessibleName("Структурований EmailDraftV2, JSON")
        self.source.setPlainText(draft.model_dump_json(indent=2))
        self.highlighter = JsonHighlighter(self.source.document())
        self.tabs.addTab(self.source, "Структура (JSON) · канонічна")
        self.html_source = QPlainTextEdit()
        self.html_source.setReadOnly(True)
        self.html_source.setTabChangesFocus(True)
        self.html_source.setFont(self.source.font())
        self.html_source.setAccessibleName(
            "HTML-проєкція вмісту вибраного листа, не код Qt"
        )
        self.html_source.setPlainText(render_email_html(draft, selected_index))
        self.html_highlighter = HtmlHighlighter(self.html_source.document())
        self.tabs.addTab(self.html_source, "HTML-проєкція листа")
        actions = QHBoxLayout()
        self.copy_button = QPushButton("Копіювати JSON")
        self.copy_button.clicked.connect(self.copy_current)
        self.tabs.currentChanged.connect(
            lambda index: self.copy_button.setText(
                "Копіювати JSON" if index == 0 else "Копіювати HTML"
            )
        )
        actions.addWidget(self.copy_button)
        close = QPushButton("Закрити")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)

    def copy_current(self) -> None:
        field = self.source if self.tabs.currentIndex() == 0 else self.html_source
        QApplication.clipboard().setText(field.toPlainText())

    def clear_sources(self) -> None:
        self.source.clear()
        self.html_source.clear()
