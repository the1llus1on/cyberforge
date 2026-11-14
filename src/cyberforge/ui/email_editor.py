"""Native message fields; Apply updates a candidate, never the database."""

import json
from collections.abc import Callable

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from cyberforge.agents.contracts import MessageV1
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.contracts import GenerationError
from cyberforge.ui.pages import label


class EmailEditorDialog(QDialog):
    def __init__(
        self, message: MessageV1, apply: Callable[[MessageV1], None], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Редагувати лист")
        self.resize(620, 520)
        self._apply = apply
        layout = QVBoxLayout(self)
        layout.addWidget(
            label(
                "Застосувати — змінити незбережену чернетку. "
                "Скасувати — відкинути ці правки. "
                "Запис у SQLite виконує лише «Зберегти» в конструкторі."
            )
        )
        form = QFormLayout()
        self.fields = {}
        for name, title, limit in (
            ("sender_name", "Синтетичне ім’я відправника", 200),
            ("sender_address", "Адреса відправника (.invalid)", 254),
            ("subject", "Тема", 300),
        ):
            field = QLineEdit(getattr(message, name))
            # Existing valid legacy messages can exceed the editor's narrower
            # Apply bounds. Never silently truncate them when opening a dialog.
            field.setMaxLength(max(limit, len(getattr(message, name))))
            field.setToolTip(f"Після редагування: не більше {limit} символів.")
            field.setAccessibleName(title)
            form.addRow(title, field)
            self.fields[name] = field
        self.body = QPlainTextEdit(message.body_text)
        self.body.setAccessibleName("Текст листа (до 4000 символів)")
        form.addRow("Текст (до 4000 символів)", self.body)
        layout.addLayout(form, 1)
        self.error = label("")
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).setText(
            "Застосувати до чернетки"
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Скасувати правки"
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.apply
        )
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def apply(self):
        try:
            value = MessageV1.model_validate_json(
                json.dumps(
                    {name: field.text() for name, field in self.fields.items()}
                    | {"body_text": self.body.toPlainText()}
                )
            )
            self._apply(value)
        except (ValidationError, GenerationError, ApplicationError, ValueError):
            self.error.setText(
                "Правки відхилено: потрібні непорожні обмежені поля, синтетична адреса "
                ".invalid і звичайний текст без коду, секретів та зовнішніх ресурсів. "
                "Сценарій також має залишатися доступним для редагування."
            )
            return
        self.accept()
