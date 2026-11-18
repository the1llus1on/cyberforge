"""Administrator controls for the Windows vault and explicit provider activation."""

from collections.abc import Callable

from pydantic import SecretStr
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.provider_settings import ProviderSettings
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.config import APPROVED_MODELS
from cyberforge.llm.contracts import Provider
from cyberforge.ui.pages import label


class ProviderPage(QWidget):
    def __init__(
        self, service: ProviderSettings, token: Callable[[], str | None]
    ) -> None:
        super().__init__()
        self.service, self.token = service, token
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItem("Офлайн · Mock", Provider.MOCK)
        self.provider.addItem("Groq", Provider.GROQ)
        self.provider.addItem("Gemini", Provider.GEMINI)
        self.model = QComboBox()
        self.key = QLineEdit()
        self.key.setMaxLength(512)
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Провайдер", self.provider)
        form.addRow("Модель", self.model)
        form.addRow("Новий ключ API", self.key)
        layout.addLayout(form)
        actions = (
            ("Зберегти ключ", self._save),
            ("Вилучити ключ", self._delete),
            ("Перевірити з’єднання", self._probe),
            ("Активувати обраний режим", self._activate),
        )
        for text, action in actions:
            button = QPushButton(text)
            button.clicked.connect(action)
            layout.addWidget(button)
        self.message = label("")
        layout.addWidget(self.message)
        self.status = label("")
        self.status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.status)
        layout.addStretch()
        self.provider.currentIndexChanged.connect(self._models)
        self._models()

    def _models(self) -> None:
        self.model.clear()
        self.model.addItems(
            sorted(APPROVED_MODELS[Provider(self.provider.currentData())])
        )

    def _run(self, operation, success: str) -> None:
        try:
            operation()
            self.refresh()
        except ApplicationError as error:
            self.message.setText(str(error))
        else:
            self.message.setText(success)
        finally:
            self.key.clear()

    def _save(self) -> None:
        self._run(
            lambda: self.service.replace_key(
                self.token(), self.provider.currentData(), SecretStr(self.key.text())
            ),
            "Ключ збережено. Активуйте потрібний режим окремо.",
        )

    def _delete(self) -> None:
        self._run(
            lambda: self.service.replace_key(
                self.token(), self.provider.currentData(), None
            ),
            "Ключ вилучено.",
        )

    def _probe(self) -> None:
        self._run(
            lambda: self.service.probe(
                self.token(), self.provider.currentData(), self.model.currentText()
            ),
            "Синтетична перевірка з’єднання успішна.",
        )

    def _activate(self) -> None:
        provider = self.provider.currentData()
        self._run(
            lambda: self.service.activate(
                self.token(),
                provider if provider != Provider.MOCK else None,
                self.model.currentText(),
            ),
            "Поточний режим збережено.",
        )

    def refresh(self) -> None:
        try:
            profile, provider, model, saved = self.service.status(self.token())
            revision = self.service.active_revision(self.token())
        except ApplicationError as error:
            self.status.setText(str(error))
            return
        route = f"{provider} / {model}" if provider else "Mock"
        names = ", ".join(saved) or "немає"
        self.status.setText(
            f"Активний режим: {route}\nКлючі збережено для: {names}\nПрофіль: {profile}"
            + (f"\nРевізія активного ключа: {revision}" if revision else "")
        )

    def clear(self) -> None:
        self.key.clear()
        self.message.clear()
        self.status.clear()
