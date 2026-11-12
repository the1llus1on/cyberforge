"""Scenario form with explicit saves and a single unsaved-edit guard."""

import json
from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.domain.scenarios import Difficulty, Scenario
from cyberforge.ui.pages import label


class ScenarioPage(QWidget):
    saved = Signal(object)

    def __init__(
        self, service: ScenarioService, token: Callable[[], str | None]
    ) -> None:
        super().__init__()
        self.service = service
        self.token = token
        self.scenario: Scenario | None = None
        self.active = False
        self.editable = False
        self._baseline: tuple = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        self.title = label("Сценарій не вибрано", "title")
        layout.addWidget(self.title)
        self.metadata = label("Створіть сценарій або виберіть його в каталозі.")
        layout.addWidget(self.metadata)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        basic, advanced = QFormLayout(), QFormLayout()
        for title, form in (("Параметри", basic), ("Розширені", advanced)):
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            content = QWidget()
            content.setLayout(form)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content)
            self.tabs.addTab(scroll, title)
        self.topic = QPlainTextEdit()
        self.topic.setFixedHeight(85)
        self.audience = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setFixedHeight(85)
        self.difficulty_group = QButtonGroup(self)
        self.difficulties: dict[Difficulty, QRadioButton] = {}
        choices = QWidget()
        row = QHBoxLayout(choices)
        row.setContentsMargins(0, 0, 0, 0)
        for difficulty in Difficulty:
            control = QRadioButton(difficulty.label)
            self.difficulty_group.addButton(control)
            self.difficulties[difficulty] = control
            row.addWidget(control)
            control.toggled.connect(self._changed)
        basic.addRow("Тема * (до 2000 символів)", self.topic)
        basic.addRow("Бажана складність *", choices)
        basic.addRow("Навчальна аудиторія (необов’язково, до 1000)", self.audience)
        basic.addRow("Додатковий опис (необов’язково, до 10000)", self.description)
        self.learning_objective = QPlainTextEdit()
        self.tactics = QPlainTextEdit()
        self.nist_cues = QPlainTextEdit()
        self.generation_parameters = QPlainTextEdit()
        for field in (
            self.learning_objective,
            self.tactics,
            self.nist_cues,
            self.generation_parameters,
        ):
            field.setFixedHeight(75)
        advanced.addRow("Навчальна мета (до 10000 символів)", self.learning_objective)
        advanced.addRow("Бажані тактики — по одній у рядку", self.tactics)
        advanced.addRow(
            "Бажані ознаки NIST для листа — по одній у рядку", self.nist_cues
        )
        advanced.addRow(
            label(
                "Тактики й ознаки: до 100 записів по 200 символів. "
                "Це побажання викладача; фактична наявність ще не перевірялася."
            )
        )
        advanced.addRow(
            "Додаткові параметри генерації (JSON-об’єкт)", self.generation_parameters
        )
        advanced.addRow(
            label("Параметри зберігаються як дані. Загальний ліміт — 50 000 символів.")
        )
        self.materials = label(
            "Електронний лист: Не створено\nВебсторінка: Не створено\n"
            "Генерація та публікація будуть доступні на наступних етапах."
        )
        layout.addWidget(self.materials)
        self.message = label("")
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.save_button = QPushButton("Зберегти")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        self.revert_button = QPushButton("Скасувати зміни")
        self.revert_button.clicked.connect(self.revert)
        actions.addWidget(self.save_button)
        actions.addWidget(self.revert_button)
        layout.addLayout(actions)
        for field in (
            self.topic,
            self.audience,
            self.description,
            self.learning_objective,
            self.tactics,
            self.nist_cues,
            self.generation_parameters,
        ):
            field.textChanged.connect(self._changed)
        self.clear()

    def heightForWidth(self, width: int) -> int:
        return self.layout().minimumHeightForWidth(width)

    def _raw(self) -> tuple:
        return (
            self.topic.toPlainText(),
            self.audience.text(),
            self.description.toPlainText(),
            self.learning_objective.toPlainText(),
            self.tactics.toPlainText(),
            self.nist_cues.toPlainText(),
            self.generation_parameters.toPlainText(),
            next(
                (d.value for d, c in self.difficulties.items() if c.isChecked()), None
            ),
        )

    @property
    def dirty(self) -> bool:
        return self.active and self.editable and self._raw() != self._baseline

    def _changed(self) -> None:
        self.save_button.setEnabled(self.active and self.editable)
        self.revert_button.setEnabled(self.dirty)
        self.title.setText(
            (self.scenario.name if self.scenario else "Новий сценарій")
            + (" · Незбережені зміни" if self.dirty else "")
            if self.active
            else "Сценарій не вибрано"
        )

    def clear(self) -> None:
        self.active = self.editable = False
        self.scenario = None
        self._fill()
        self.metadata.setText("Створіть сценарій або виберіть його в каталозі.")
        self.tabs.setEnabled(False)
        self.materials.setVisible(False)

    def _set_editable(self) -> None:
        self.tabs.setEnabled(self.active)
        for field in (
            self.topic,
            self.audience,
            self.description,
            self.learning_objective,
            self.tactics,
            self.nist_cues,
            self.generation_parameters,
        ):
            field.setReadOnly(not self.editable)
        for control in self.difficulties.values():
            control.setEnabled(self.editable)

    def _fill(self) -> None:
        parameters = self.scenario.parameters if self.scenario else None
        self.topic.setPlainText(parameters.topic if parameters else "")
        self.audience.setText(parameters.audience if parameters else "")
        for field, name in (
            (self.description, "description"),
            (self.learning_objective, "learning_objective"),
        ):
            field.setPlainText(getattr(parameters, name) if parameters else "")
        self.tactics.setPlainText("\n".join(parameters.tactics) if parameters else "")
        self.nist_cues.setPlainText(
            "\n".join(parameters.nist_cues) if parameters else ""
        )
        self.generation_parameters.setPlainText(
            json.dumps(
                parameters.generation_parameters if parameters else {},
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )
        self.difficulties[
            parameters.difficulty if parameters else Difficulty.BEGINNER
        ].setChecked(True)
        self._baseline = self._raw()
        self.message.clear()
        self._changed()

    def new(self) -> None:
        self.scenario = None
        self.active = self.editable = True
        self._set_editable()
        self._fill()
        self.metadata.setText("ID буде присвоєно після успішного збереження.")
        self.materials.setVisible(True)
        self.topic.setFocus()

    def load(self, scenario: Scenario, *, editable: bool) -> None:
        self.scenario = scenario
        self.active = True
        self.editable = editable
        self._set_editable()
        self._fill()
        self.metadata.setText(
            f"ID: {scenario.id} · Автор ID: {scenario.owner_id}\n"
            f"Версія {scenario.version} · Ревізія {scenario.revision} · "
            f"{scenario.status.label}\n"
            f"Створено: {scenario.created_at.astimezone():%d.%m.%Y %H:%M} · "
            f"Змінено: {scenario.updated_at.astimezone():%d.%m.%Y %H:%M}"
            + ("\nЛише перегляд: сценарій іншого автора." if not editable else "")
        )
        self.materials.setVisible(True)

    def save(self) -> bool:
        if not self.active or not self.editable:
            return False
        try:
            try:
                extra = json.loads(self.generation_parameters.toPlainText())
            except (ValueError, RecursionError):
                raise ApplicationError(
                    "Додаткові параметри мають бути JSON-об’єктом."
                ) from None
            parameters = dict(
                topic=self.topic.toPlainText(),
                difficulty=self._raw()[-1],
                audience=self.audience.text(),
                description=self.description.toPlainText(),
                learning_objective=self.learning_objective.toPlainText(),
                tactics=tuple(
                    line.strip()
                    for line in self.tactics.toPlainText().splitlines()
                    if line.strip()
                ),
                nist_cues=tuple(
                    line.strip()
                    for line in self.nist_cues.toPlainText().splitlines()
                    if line.strip()
                ),
                generation_parameters=extra,
            )
            if self.scenario is None:
                saved = self.service.create(self.token(), parameters)
            else:
                saved = self.service.update(
                    self.token(),
                    self.scenario.id,
                    parameters,
                    expected_version=self.scenario.version,
                    expected_revision=self.scenario.revision,
                )
        except ApplicationError as error:
            self.message.setText(str(error))
            return False
        self.load(saved, editable=True)
        self.message.setText("Параметри збережено.")
        self.saved.emit(saved)
        return True

    def ask_unsaved(self) -> QMessageBox.StandardButton:
        box = QMessageBox(self)
        box.setWindowTitle("Незбережені зміни")
        box.setText("Зберегти зміни сценарію перед переходом?")
        for standard, text in (
            (QMessageBox.StandardButton.Save, "Зберегти"),
            (QMessageBox.StandardButton.Discard, "Відкинути зміни"),
            (QMessageBox.StandardButton.Cancel, "Залишитися"),
        ):
            box.addButton(standard).setText(text)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return QMessageBox.StandardButton(box.exec())

    def can_leave(self) -> bool:
        if not self.dirty:
            return True
        choice = self.ask_unsaved()
        if choice == QMessageBox.StandardButton.Save:
            return self.save()
        if choice == QMessageBox.StandardButton.Discard:
            self._fill()
            return True
        return False

    def revert(self) -> None:
        # Uses the same explicit decision even when Cancel is clicked in the form.
        self.can_leave()
