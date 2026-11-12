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
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.domain.scenarios import Difficulty, Scenario
from cyberforge.ui.cue_picker import CuePicker
from cyberforge.ui.pages import card, label


class ScenarioPage(QWidget):
    saved = Signal(object)
    archive_changed = Signal(object)

    def __init__(
        self, service: ScenarioService, token: Callable[[], str | None]
    ) -> None:
        super().__init__()
        self.service = service
        self.token = token
        self.scenario: Scenario | None = None
        self.observed: Scenario | None = None
        self.owned = False
        self.active = False
        self.editable = False
        self._baseline: tuple = ()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.content_stack = QStackedWidget()
        outer.addWidget(self.content_stack)
        self.empty_state = QWidget()
        empty = QVBoxLayout(self.empty_state)
        empty.setContentsMargins(36, 32, 36, 32)
        empty.addStretch()
        self.empty_card = card(
            "Сценарій не вибрано",
            "Виберіть сценарій зі списку або натисніть «+ Новий сценарій», "
            "щоб розпочати створення.",
        )
        self.empty_card.setMaximumWidth(760)
        centered = QHBoxLayout()
        centered.addStretch()
        centered.addWidget(self.empty_card, 10)
        centered.addStretch()
        empty.addLayout(centered)
        empty.addStretch()
        self.editor = QWidget()
        self.content_stack.addWidget(self.empty_state)
        self.content_stack.addWidget(self.editor)
        layout = QVBoxLayout(self.editor)
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
        self.nist_cues = CuePicker()
        self.nist_cues.changed.connect(self._changed)
        self.legacy_cues = QPlainTextEdit()
        self.legacy_cues.setReadOnly(True)
        self.legacy_cues.setFixedHeight(75)
        self.legacy_hint = label(
            "Старі некласифіковані значення збережено нижче. "
            "Вони не є підтвердженим вибором NIST; оберіть відповідні ознаки вручну."
        )
        self.generation_parameters = QPlainTextEdit()
        for field in (
            self.learning_objective,
            self.tactics,
            self.generation_parameters,
        ):
            field.setFixedHeight(75)
        advanced.addRow("Навчальна мета (до 10000 символів)", self.learning_objective)
        advanced.addRow("Бажані тактики — по одній у рядку", self.tactics)
        advanced.addRow("Бажані ознаки листа — NIST TN 2276 (2023)", self.nist_cues)
        advanced.addRow(self.legacy_hint)
        advanced.addRow(self.legacy_cues)
        advanced.addRow(
            label(
                "Власні тактики: до 100 записів по 200 символів. "
                "Ознаки обираються позначками або клавішею Space. Це бажані ознаки; "
                "їхню наявність у матеріалах ще не перевірено."
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
        archive_actions = QHBoxLayout()
        self.archive_button = QPushButton("Архівувати сценарій")
        self.archive_button.clicked.connect(self.archive)
        self.restore_button = QPushButton("Відновити з архіву")
        self.restore_button.clicked.connect(self.restore)
        archive_actions.addWidget(self.archive_button)
        archive_actions.addWidget(self.restore_button)
        layout.addLayout(archive_actions)
        for field in (
            self.topic,
            self.audience,
            self.description,
            self.learning_objective,
            self.tactics,
            self.generation_parameters,
        ):
            field.textChanged.connect(self._changed)
        self.clear()

    def heightForWidth(self, width: int) -> int:
        # The stack's preferred editor height must not push footer actions out
        # of the viewport; keep the existing minimum-height scroll behavior.
        content = self.editor if self.active else self.empty_state
        return content.layout().minimumHeightForWidth(width)

    def _raw(self) -> tuple:
        return (
            self.topic.toPlainText(),
            self.audience.text(),
            self.description.toPlainText(),
            self.learning_objective.toPlainText(),
            self.tactics.toPlainText(),
            self.nist_cues.selected(),
            self.generation_parameters.toPlainText(),
            next(
                (d.value for d, c in self.difficulties.items() if c.isChecked()), None
            ),
        )

    @property
    def dirty(self) -> bool:
        return self.active and self._raw() != self._baseline

    def _changed(self) -> None:
        self.content_stack.setCurrentWidget(
            self.editor if self.active else self.empty_state
        )
        self.save_button.setEnabled(self.active and self.editable)
        self.revert_button.setEnabled(self.dirty)
        state = self.observed or self.scenario
        self.archive_button.setVisible(
            self.active and self.owned and state is not None and not state.archived
        )
        self.restore_button.setVisible(
            self.active and self.owned and state is not None and state.archived
        )
        self.title.setText(
            (self.scenario.name if self.scenario else "Новий сценарій")
            + (" · Незбережені зміни" if self.dirty else "")
            if self.active
            else "Сценарій не вибрано"
        )

    def clear(self) -> None:
        self.active = self.editable = False
        self.scenario = None
        self.observed = None
        self.owned = False
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
            self.generation_parameters,
        ):
            field.setReadOnly(not self.editable)
        for control in self.difficulties.values():
            control.setEnabled(self.editable)
        self.nist_cues.set_read_only(not self.editable)

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
        self.nist_cues.set_selected(parameters.nist_cues if parameters else ())
        self.legacy_cues.setPlainText(
            "\n".join(parameters.legacy_nist_cues) if parameters else ""
        )
        self.legacy_hint.setVisible(bool(parameters and parameters.legacy_nist_cues))
        self.legacy_cues.setVisible(bool(parameters and parameters.legacy_nist_cues))
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
        self.observed = None
        self.owned = True
        self.active = self.editable = True
        self._set_editable()
        self._fill()
        self.metadata.setText("ID буде присвоєно після успішного збереження.")
        self.materials.setVisible(True)
        self.topic.setFocus()

    def load(self, scenario: Scenario, *, editable: bool) -> None:
        self.scenario = scenario
        self.observed = scenario
        self.owned = editable
        self.active = True
        self.editable = editable and not scenario.archived
        self._set_editable()
        self._fill()
        self.metadata.setText(
            f"ID: {scenario.id} · Автор ID: {scenario.owner_id}\n"
            f"Версія {scenario.version} · Ревізія {scenario.revision} · "
            f"{scenario.status.label}\n"
            f"Створено: {scenario.created_at.astimezone():%d.%m.%Y %H:%M} · "
            f"Змінено: {scenario.updated_at.astimezone():%d.%m.%Y %H:%M}"
            + (
                f"\nАрхівовано: {scenario.archived_at.astimezone():%d.%m.%Y %H:%M}"
                if scenario.archived_at
                else "\nАктивний сценарій"
            )
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
                nist_cues=self.nist_cues.selected(),
                legacy_nist_cues=self.scenario.parameters.legacy_nist_cues
                if self.scenario
                else (),
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
                    expected_archive_revision=self.scenario.archive_revision,
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
        if self.dirty and self.confirm_revert():
            if self.scenario is None:
                self._fill()
            else:
                try:
                    self.load(
                        self.service.get(self.token(), self.scenario.id),
                        editable=self.owned,
                    )
                except ApplicationError as error:
                    self.message.setText(str(error))

    def confirm_revert(self) -> bool:
        return self._confirm(
            "Скасувати зміни",
            "Відкинути незбережені зміни сценарію?",
            "Відкинути зміни",
        )

    def confirm_archive(self) -> bool:
        return self._confirm(
            "Архівувати сценарій",
            "Архівувати сценарій? Його можна буде відновити з архіву.",
            "Архівувати",
        )

    def _confirm(self, title: str, text: str, accept: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        action = box.addButton(accept, QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton("Залишитися", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() == action

    def archive(self) -> bool:
        return self._archive_change(archived=True)

    def restore(self) -> bool:
        return self._archive_change(archived=False)

    def _archive_change(self, *, archived: bool) -> bool:
        if not self.active or not self.owned or self.scenario is None:
            return False
        if archived and not self.confirm_archive():
            return False
        if not self.can_leave() or self.scenario is None:
            return False
        state = self.observed or self.scenario
        try:
            action = self.service.archive if archived else self.service.restore
            changed = action(
                self.token(),
                state.id,
                expected_version=state.version,
                expected_revision=state.revision,
                expected_archive_revision=state.archive_revision,
            )
        except ApplicationError as error:
            self.message.setText(str(error))
            return False
        self.load(changed, editable=True)
        self.archive_changed.emit(changed)
        self.message.setText(
            "Сценарій архівовано." if archived else "Сценарій відновлено."
        )
        return True

    def observe(self, scenario: Scenario) -> None:
        """Lock an externally archived editor without erasing its recovery buffer."""
        if self.scenario is None or self.scenario.id != scenario.id:
            return
        if (
            self.observed
            and self.observed.archive_revision == scenario.archive_revision
        ):
            return
        if not self.dirty:
            self.load(scenario, editable=self.owned)
        else:
            self.observed = scenario
            self.editable = self.owned and not scenario.archived
            self._set_editable()
            self._changed()
            self.message.setText(
                "Стан архіву змінено в іншому вікні. Правки залишено для копіювання; "
                "відкиньте їх і повторно відкрийте актуальний сценарій "
                "перед збереженням."
            )
