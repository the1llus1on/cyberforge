"""Scenario form with explicit saves and a single unsaved-edit guard."""

import json
from collections.abc import Callable

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.email_materials import EmailMaterialService, MaterialState
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import ScenarioPublicationService
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.domain.scenarios import Difficulty, Scenario
from cyberforge.ui.cue_picker import CuePicker
from cyberforge.ui.email_page import EmailPage
from cyberforge.ui.pages import card, label
from cyberforge.ui.scenario_integration import IntegrationDialog
from cyberforge.ui.web_page import WebPage


class _WorkspaceStack(QStackedWidget):
    """A hidden constructor must not impose its height on the scenario card."""

    def __init__(self) -> None:
        super().__init__()
        self.currentChanged.connect(lambda _: self.updateGeometry())

    def minimumSizeHint(self) -> QSize:
        current = self.currentWidget()
        return current.minimumSizeHint() if current else super().minimumSizeHint()

    def sizeHint(self) -> QSize:
        current = self.currentWidget()
        return current.sizeHint() if current else super().sizeHint()


class ScenarioPage(QWidget):
    saved = Signal(object)
    archive_changed = Signal(object)

    def __init__(
        self,
        service: ScenarioService,
        token: Callable[[], str | None],
        emails: EmailMaterialService,
        webs: WebMaterialService | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.token = token
        self.emails = emails
        self.webs = webs or WebMaterialService(emails)
        self.integration = ScenarioIntegrationService(self.webs)
        self.readiness = ScenarioReadinessService(self.integration)
        self.publications = ScenarioPublicationService(self.readiness)
        self.integration_dialog: IntegrationDialog | None = None
        self.scenario: Scenario | None = None
        self.observed: Scenario | None = None
        self.owned = False
        self.active = False
        self.editable = False
        self._baseline: tuple = ()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.content_stack = _WorkspaceStack()
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
        self.email_page = EmailPage(emails, token)
        self.content_stack.addWidget(self.email_page)
        self.email_page.back_requested.connect(self.close_email)
        self.email_page.saved.connect(self._email_saved)
        self.email_page.state_changed.connect(self._email_state)
        self.web_page = WebPage(self.webs, token)
        self.content_stack.addWidget(self.web_page)
        self.web_page.back_requested.connect(self.close_web)
        self.web_page.saved.connect(self._web_saved)
        self.web_page.state_changed.connect(self._web_state)
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
        self.materials = QWidget()
        material_layout = QHBoxLayout(self.materials)
        material_layout.setContentsMargins(0, 0, 0, 0)
        self.email_material = QFrame()
        self.email_material.setObjectName("emailMaterial")
        email_layout = QVBoxLayout(self.email_material)
        email_layout.addWidget(label("Електронний лист", "heading"))
        self.email_status = label(MaterialState.EMPTY)
        email_layout.addWidget(self.email_status)
        self.email_progress = QProgressBar()
        self.email_progress.setRange(0, 0)
        self.email_progress.hide()
        email_layout.addWidget(self.email_progress)
        self.email_button = QPushButton("Створити електронний лист")
        self.email_button.clicked.connect(self.open_email)
        email_layout.addWidget(self.email_button)
        material_layout.addWidget(self.email_material, 1)
        self.web_material = QFrame()
        self.web_material.setObjectName("webMaterial")
        web_layout = QVBoxLayout(self.web_material)
        web_layout.addWidget(label("Вебсторінка", "heading"))
        self.web_status = label(MaterialState.EMPTY)
        web_layout.addWidget(self.web_status)
        self.web_button = QPushButton("Створити сайт")
        self.web_button.clicked.connect(self.open_web)
        web_layout.addWidget(self.web_button)
        material_layout.addWidget(self.web_material, 1)
        layout.addWidget(self.materials)
        self.integration_panel = QWidget()
        integration_layout = QVBoxLayout(self.integration_panel)
        integration_layout.setContentsMargins(0, 0, 0, 0)
        integration_layout.setSpacing(3)
        self.integration_status = label("")
        integration_layout.addWidget(self.integration_status)
        integration_actions = QHBoxLayout()
        self.integration_button = QPushButton("Зв’язок · Рубрика · Публікація")
        self.integration_button.clicked.connect(self.open_integration)
        self.new_version_button = QPushButton("Створити нову версію")
        self.new_version_button.clicked.connect(self.create_next_version)
        integration_actions.addWidget(self.integration_button)
        integration_actions.addWidget(self.new_version_button)
        integration_layout.addLayout(integration_actions)
        layout.addWidget(self.integration_panel)
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
        content = self.content_stack.currentWidget()
        return content.layout().minimumHeightForWidth(width)

    def _email_state(self, state: MaterialState) -> None:
        self.email_status.setText(state)
        color = (
            "#69c994"
            if state == MaterialState.SAVED
            else "#d9b770"
            if state == MaterialState.REVIEW
            else "#343843"
        )
        self.email_material.setStyleSheet(
            f"QFrame#emailMaterial {{ border: 1px solid {color}; "
            "border-radius: 12px; }"
        )
        self.email_material.setProperty("saved", state == MaterialState.SAVED)
        self.email_progress.setVisible(state == MaterialState.GENERATING)

    def refresh_materials(self) -> None:
        self.email_button.setEnabled(self.scenario is not None)
        state = MaterialState.EMPTY
        if self.scenario is not None:
            try:
                state = self.emails.load(self.token(), self.scenario).state
            except ApplicationError:
                state = MaterialState.REVIEW
        self._email_state(state)
        self.email_button.setText(
            "Створити електронний лист"
            if state == MaterialState.EMPTY and self.editable
            else "Відкрити електронний лист"
        )
        self.email_button.setToolTip(
            "Спочатку збережіть параметри сценарію."
            if self.scenario is None
            else "Відкрити конструктор листа"
        )
        web_state = MaterialState.EMPTY
        if self.scenario is not None:
            try:
                web_state = self.webs.load(self.token(), self.scenario).state
            except ApplicationError:
                web_state = MaterialState.REVIEW
        self.refresh_integration()
        self._web_state(web_state)
        self.web_button.setEnabled(self.scenario is not None)
        self.web_button.setText(
            "Створити сайт" if web_state == MaterialState.EMPTY else "Відкрити сайт"
        )

    def refresh_integration(self) -> None:
        self.integration_panel.setVisible(self.scenario is not None)
        self.new_version_button.setVisible(
            bool(
                self.scenario
                and self.owned
                and self.scenario.status == "published"
                and not self.scenario.archived
            )
        )
        self.integration_status.clear()
        if self.scenario is None:
            return
        try:
            state = self.integration.inspect(self.token(), self.scenario)
            if self.scenario.status == "published":
                text = "Опубліковано · вміст незмінний · доступ груп керується окремо"
            else:
                report = self.readiness.evaluate(self.token(), self.scenario)
                text = (
                    "Технічно готово · потрібні групи й підтвердження"
                    if report.technical_ready
                    else "Ще не готово до публікації"
                )
            self.integration_status.setText(
                f"Зв’язок: {'збережено' if state.link else 'потребує налаштування'} · "
                f"Рубрика: {'збережено' if state.rubric else 'не збережено'}\n" + text
            )
        except ApplicationError as error:
            self.integration_status.setText(str(error))

    def open_integration(self) -> None:
        if self.integration_dialog is not None:
            self.integration_dialog.raise_()
            self.integration_dialog.activateWindow()
            return
        if self.scenario is None or not self.can_leave():
            return
        try:
            dialog = IntegrationDialog(
                self.integration,
                self.token,
                self.scenario,
                owned=self.owned,
                parent=self,
            )
            self.integration_dialog = dialog
            dialog.finished.connect(lambda _: self._integration_finished(dialog))
            # WebEngine may recreate the native surface on its first load. A
            # transient hide must not unwind exec() and delete a loading page.
            dialog.open()
        except ApplicationError as error:
            self.message.setText(str(error))

    def _integration_finished(self, dialog: IntegrationDialog) -> None:
        if self.integration_dialog is dialog:
            self.integration_dialog = None
        dialog.deleteLater()
        if (
            dialog.forced
            or dialog.session_token != self.token()
            or self.scenario is None
            or self.scenario.id != dialog.expected.id
        ):
            return
        try:
            current = self.service.get(self.token(), self.scenario.id)
            self.load(current, editable=self.owned)
            if dialog.changed:
                self.saved.emit(current)
        except ApplicationError as error:
            self.message.setText(str(error))

    def create_next_version(self) -> None:
        if self.scenario is None or not self.can_leave():
            return
        try:
            current = self.service.create_next_draft(self.token(), self.scenario)
            self.load(current, editable=self.owned)
            self.message.setText(
                "Створено нову чернетку без матеріалів і доступів. Попередня "
                "публікація збережена."
            )
            self.saved.emit(current)
        except ApplicationError as error:
            self.message.setText(str(error))

    def _web_state(self, state: MaterialState) -> None:
        self.web_status.setText(state)
        color = (
            "#69c994"
            if state == MaterialState.SAVED
            else ("#d9b770" if state == MaterialState.REVIEW else "#343843")
        )
        self.web_material.setStyleSheet(
            f"QFrame#webMaterial {{ border:1px solid {color}; border-radius:12px; }}"
        )
        self.web_material.setProperty("saved", state == MaterialState.SAVED)

    def open_web(self) -> None:
        if self.scenario is None or not self.can_leave():
            return
        try:
            self.web_page.open(self.scenario, editable=self.editable)
        except ApplicationError as error:
            self.message.setText(str(error))
            return
        self.content_stack.setCurrentWidget(self.web_page)

    def close_web(self) -> None:
        if self.web_page.can_leave() and self.scenario is not None:
            try:
                self.load(
                    self.service.get(self.token(), self.scenario.id),
                    editable=self.owned,
                )
            except ApplicationError as error:
                self.web_page.message.setText(str(error))

    def _web_saved(self, scenario: Scenario) -> None:
        self.load(scenario, editable=self.owned)
        self.message.setText("Сайт збережено. Сценарій ще не опубліковано.")
        self.saved.emit(scenario)

    def open_email(self) -> None:
        if self.scenario is None or not self.can_leave():
            return
        try:
            self.email_page.open(self.scenario, editable=self.editable)
            self.email_page.preview.set_link(
                self.integration.inspect(self.token(), self.scenario).link
            )
        except ApplicationError as error:
            self.message.setText(str(error))
            return
        self.content_stack.setCurrentWidget(self.email_page)
        if self.email_page.draft is None and self.editable:
            self.email_page.generate()

    def close_email(self) -> None:
        if self.email_page.can_leave() and self.scenario is not None:
            try:
                self.load(
                    self.service.get(self.token(), self.scenario.id),
                    editable=self.owned,
                )
            except ApplicationError as error:
                self.email_page.message.setText(str(error))

    def _email_saved(self, scenario: Scenario) -> None:
        self.load(scenario, editable=self.owned)
        self.message.setText("Електронний лист збережено. Сценарій ще не опубліковано.")
        self.saved.emit(scenario)

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
        if self.content_stack.currentWidget() not in (self.email_page, self.web_page):
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
        for dialog in self.findChildren(IntegrationDialog):
            dialog.force_close()
        self.integration_panel.hide()
        self.email_page.clear()
        self.web_page.clear()
        self.content_stack.setCurrentWidget(self.empty_state)
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
        self.email_page.clear()
        self.web_page.clear()
        self.content_stack.setCurrentWidget(self.editor)
        self.scenario = None
        self.observed = None
        self.owned = True
        self.active = self.editable = True
        self._set_editable()
        self._fill()
        self.metadata.setText("ID буде присвоєно після успішного збереження.")
        self.materials.setVisible(True)
        self.refresh_materials()
        self.topic.setFocus()

    def load(self, scenario: Scenario, *, editable: bool) -> None:
        self.email_page.clear()
        self.web_page.clear()
        self.content_stack.setCurrentWidget(self.editor)
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
        self.refresh_materials()

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
        if not self.web_page.can_leave():
            return False
        if not self.email_page.can_leave():
            return False
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
        if self.content_stack.currentWidget() == self.web_page:
            self.web_page.observe(scenario)
            return
        if self.content_stack.currentWidget() == self.email_page:
            self.email_page.observe(scenario)
            return
        if (self.scenario.version, self.scenario.revision) != (
            scenario.version,
            scenario.revision,
        ):
            self._email_state(MaterialState.REVIEW)
        else:
            self.refresh_materials()
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
