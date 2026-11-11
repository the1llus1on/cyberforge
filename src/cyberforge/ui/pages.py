"""Honest empty workspace views; no fabricated learners or scenario results."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cyberforge.ui.navigation import View


def label(text: str, kind: str = "muted") -> QLabel:
    widget = QLabel(text)
    widget.setProperty("kind", kind)
    widget.setWordWrap(True)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def card(title: str, text: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    layout.addWidget(label(title, "heading"))
    layout.addWidget(label(text))
    return frame


class WorkspacePage(QWidget):
    profile_requested = Signal()

    def __init__(self, view: View) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(760)
        body = QVBoxLayout(content)
        body.setSpacing(22)
        body.setContentsMargins(0, 0, 0, 0)
        eyebrow, title, description = {
            View.GUEST: (
                "НАВЧАЙТЕСЯ РОЗПІЗНАВАТИ ЗАГРОЗИ",
                "Вітаємо в CyberForge",
                "Безпечний простір для навчання кібергігієни. "
                "Досліджуйте соціальну інженерію через навчальні листи, "
                "вебсценарії та зворотний зв’язок.",
            ),
            View.CONSTRUCTOR: (
                "РОБОЧИЙ ПРОСТІР / КОНСТРУКТОР",
                "Від задуму до сценарію",
                "Єдиний простір для параметрів сценарію, навчального листа "
                "та пов’язаної вебсторінки.",
            ),
            View.ANALYTICS: (
                "РОБОЧИЙ ПРОСТІР / АНАЛІЗ",
                "Розумійте прогрес навчання",
                "Тут відображатимуться результати проходжень і статистика "
                "вибраного сценарію. Режим аналізу призначений для перегляду.",
            ),
            View.PROFILE: (
                "ОБЛІКОВИЙ ЗАПИС",
                "Вхід до CyberForge",
                "Зараз ви працюєте як гість. Авторизація буде доступна "
                "після реалізації етапу «Користувачі та групи».",
            ),
            View.SETTINGS: (
                "НАЛАШТУВАННЯ",
                "Ваш робочий простір",
                "Темна тема · Українська мова\n"
                "Додаткові налаштування з’являться на наступних етапах.",
            ),
        }[view]
        body.addWidget(label(eyebrow, "eyebrow"))
        self.title = label(title, "title")
        body.addWidget(self.title)
        body.addWidget(label(description))
        if view == View.GUEST:
            body.addWidget(
                card(
                    "Навчальний цикл",
                    "Електронний лист  →  Вебсценарій  →  Оцінювання  →  "
                    "Зворотний зв’язок",
                )
            )
            body.addWidget(label("Увійдіть, щоб отримати доступ до ваших сценаріїв."))
        elif view == View.CONSTRUCTOR:
            body.addWidget(
                card(
                    "Сценарій не вибрано",
                    "Параметри · Електронний лист · Вебсторінка · Публікація\n\n"
                    "Це попередній перегляд оболонки. Створення й редагування "
                    "сценаріїв поки недоступні.",
                )
            )
        elif view == View.ANALYTICS:
            body.addWidget(
                card(
                    "Дані для аналізу відсутні",
                    "Сценарій не вибрано. Показники та оцінки не обчислюються.\n\n"
                    "Це попередній перегляд оболонки, без навчальних даних.",
                )
            )
        elif view == View.PROFILE:
            body.addWidget(
                card(
                    "Авторизацію ще не реалізовано",
                    "Форма входу з’явиться на наступному етапі. "
                    "Доступ до сценаріїв залишається закритим.",
                )
            )
        if view in (View.GUEST, View.CONSTRUCTOR, View.ANALYTICS):
            self.login_button = QPushButton("Перейти до входу  →")
            self.login_button.setObjectName("primary")
            self.login_button.clicked.connect(self.profile_requested)
            row = QHBoxLayout()
            row.addWidget(self.login_button)
            row.addStretch()
            body.addLayout(row)
        body.addWidget(label("Лише синтетичні навчальні матеріали. Без реальних атак."))
        layout.addWidget(content)
        layout.addStretch(2)
