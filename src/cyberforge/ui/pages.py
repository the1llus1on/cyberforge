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
            View.HOME: (
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
            View.MY_SCENARIOS: (
                "НАВЧАННЯ",
                "Мої сценарії",
                "Призначених опублікованих сценаріїв поки немає.",
            ),
            View.MY_RESULTS: (
                "РЕЗУЛЬТАТИ",
                "Мої результати",
                "Ви ще не маєте завершених проходжень. Результати не обчислюються.",
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
        self.description = label(description)
        body.addWidget(self.description)
        if view == View.HOME:
            body.addWidget(
                card(
                    "Навчальний цикл",
                    "Сценарій → Електронний лист → Вебсайт → Аналіз",
                )
            )
            self.session_hint = label(
                "«+» відкриває Конструктор, іконка графіка — Аналіз. "
                "Кнопка будинку повертає на Головну.\n"
                "Увійдіть, щоб отримати доступ до ваших сценаріїв."
            )
            body.addWidget(self.session_hint)
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
            self.scenario_info = label("Сценарій не вибрано.")
            body.addWidget(self.scenario_info)
            body.addWidget(
                card(
                    "Дані для аналізу відсутні",
                    "Для цього сценарію поки немає результатів проходження. "
                    "Показники та оцінки не обчислюються.",
                )
            )
        if view in (View.HOME, View.CONSTRUCTOR, View.ANALYTICS):
            self.login_button = QPushButton("Перейти до входу  →")
            self.login_button.setObjectName("primary")
            self.login_button.clicked.connect(self.profile_requested)
            row = QHBoxLayout()
            row.addWidget(self.login_button)
            row.addStretch()
            body.addLayout(row)
        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(content, 10)
        centered.addStretch(1)
        layout.addLayout(centered)
        layout.addStretch(2)
