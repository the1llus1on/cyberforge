"""Email Constructor: native plain-text mail template, explicit saves and workers."""

from collections.abc import Callable
from uuid import uuid4

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cyberforge.agents.contracts import EmailDraftV2, MessageV1
from cyberforge.application.email_materials import (
    EmailMaterialService,
    EmailWorkspace,
    MaterialState,
)
from cyberforge.domain.accounts import ApplicationError
from cyberforge.domain.scenarios import Scenario
from cyberforge.ui.email_editor import EmailEditorDialog
from cyberforge.ui.email_preview import MailPreview
from cyberforge.ui.email_source import EmailSourceDialog
from cyberforge.ui.email_worker import EmailWorker, RequestIdentity, WorkerSignals
from cyberforge.ui.pages import label


class EmailPage(QWidget):
    saved = Signal(object)
    back_requested = Signal()
    state_changed = Signal(object)

    def __init__(self, service: EmailMaterialService, token: Callable[[], str | None]):
        super().__init__()
        self.service, self.token = service, token
        self.workspace: EmailWorkspace | None = None
        self.draft: EmailDraftV2 | None = None
        self.unsaved = False
        self.editable = False
        self.stale = False
        self.session_epoch = uuid4().hex
        self.pending: RequestIdentity | None = None
        self._workers: dict[str, WorkerSignals] = {}
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self._timed_out)
        self._refinement_baseline = ""
        self.manual_edits = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(3)
        top = QHBoxLayout()
        self.back_button = QPushButton("← До картки сценарію")
        self.back_button.setStyleSheet("padding: 4px 10px;")
        self.back_button.clicked.connect(self.back_requested)
        top.addWidget(self.back_button)
        self.title = label("Електронний лист", "heading")
        top.addWidget(self.title, 1)
        layout.addLayout(top)
        self.provider = label(service.provider_label)
        self.provider.setStyleSheet("font-size: 12px;")
        self.status = label(MaterialState.EMPTY)
        self.status.setStyleSheet("font-size: 12px;")
        status_row = QHBoxLayout()
        status_row.addWidget(self.provider, 2)
        status_row.addWidget(self.status, 1)
        layout.addLayout(status_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setAccessibleName("Триває генерація листа")
        self.progress.hide()
        layout.addWidget(self.progress)
        # 1:18:1 = approximately 90 percent of the central content width.
        preview_row = QHBoxLayout()
        preview_row.setContentsMargins(0, 0, 0, 0)
        preview_row.addStretch(1)
        self.preview = MailPreview()
        self.messages = self.preview.messages
        self.subject = self.preview.subject
        self.sender = self.preview.sender
        self.timestamp = self.preview.timestamp
        self.body = self.preview.body
        self.resource = self.preview.resource
        self.read_messages = self.preview.read_messages
        preview_row.addWidget(self.preview, 18)
        preview_row.addStretch(1)
        layout.addLayout(preview_row, 1)
        self.message = label("")
        layout.addWidget(self.message)
        self.refinement_label = label(
            "Уточнення викладача для перегенерації (до 2000 символів)"
        )
        layout.addWidget(self.refinement_label)
        self.refinement_help = label(
            "Інструкція для наступної генерації, а не пряме редагування. "
            "Збережений лист зміниться лише після «Зберегти»."
        )
        self.refinement_help.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.refinement_help)
        self.refinement = QPlainTextEdit()
        self.refinement.setAccessibleName(
            "Інструкція для наступної перегенерації листа"
        )
        self.refinement.setPlaceholderText(
            "Наприклад: скороти основний лист і зроби прохання менш терміновим"
        )
        self.refinement.setFixedHeight(42)
        self.refinement.setTabChangesFocus(True)
        self.refinement.textChanged.connect(self._controls)
        layout.addWidget(self.refinement)
        actions = QHBoxLayout()
        self.edit_button = QPushButton("Редагувати лист")
        self.edit_button.clicked.connect(self.edit_message)
        top.addWidget(self.edit_button)
        self.refinement_scope = QComboBox()
        self.refinement_scope.addItem("AI: лише текст основного листа", "main_body")
        self.refinement_scope.addItem("AI: весь лист і фон", "all")
        self.refinement_scope.setAccessibleName("Межі змін AI; інші поля зберігаються")
        self.refinement_scope.setToolTip(
            "Лише текст: тема, відправник і всі фонові листи захищені. "
            "Суперечливу інструкцію обмежує цей вибір."
        )
        status_row.addWidget(self.refinement_scope)
        self.code_button = QPushButton("Переглянути код")
        self.code_button.clicked.connect(self.show_source)
        self.generate_button = QPushButton("Згенерувати")
        self.generate_button.clicked.connect(self.generate)
        self.save_button = QPushButton("Зберегти")
        self.save_button.setObjectName("primary")
        self.save_button.setStyleSheet("QPushButton#primary { padding: 8px 16px; }")
        self.save_button.clicked.connect(self.save)
        for control in (self.code_button, self.generate_button, self.save_button):
            if control is not self.save_button:
                control.setStyleSheet("padding: 6px 12px;")
            actions.addWidget(control)
        layout.addLayout(actions)
        # Wrapped labels must shrink to their actual height for the available
        # width, rather than reserving platform-dependent preferred line counts.
        for field in (
            self.title,
            self.provider,
            self.status,
            self.message,
            self.refinement_label,
            self.refinement_help,
        ):
            policy = field.sizePolicy()
            policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)
            policy.setHeightForWidth(field.wordWrap())
            field.setSizePolicy(policy)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._controls()

    @property
    def running(self) -> bool:
        return bool(self._workers) or self.pool.activeThreadCount() > 0

    @property
    def dirty(self) -> bool:
        return self.workspace is not None and (
            self.unsaved or self.refinement.toPlainText() != self._refinement_baseline
        )

    def _state(self, state: MaterialState) -> None:
        self.status.setText(state)
        self.state_changed.emit(state)

    def _controls(self) -> None:
        writable = self.workspace is not None and self.editable and not self.stale
        self.generate_button.setText(
            "Перегенерувати" if self.draft is not None else "Згенерувати"
        )
        self.generate_button.setEnabled(
            writable and self.service.available and not self.running
        )
        self.save_button.setEnabled(writable and self.unsaved and self.pending is None)
        self.code_button.setEnabled(self.draft is not None)
        self.edit_button.setEnabled(
            writable and self.draft is not None and not self.running
        )
        self.refinement_scope.setEnabled(writable and not self.running)
        self.refinement.setReadOnly(not writable or self.pending is not None)

    def open(self, scenario: Scenario, *, editable: bool) -> None:
        workspace = self.service.load(self.token(), scenario)
        self.clear()
        self.workspace, self.draft = workspace, workspace.draft
        self.editable = (
            editable and not scenario.archived and scenario.status == "draft"
        )
        self.title.setText(f"{scenario.name} · Лист · v{scenario.version}")
        self._state(workspace.state)
        if workspace.state == MaterialState.REVIEW:
            self.message.setText(
                "Збережений лист застарів або не пройшов перевірку. "
                "Потрібна нова генерація."
            )
        self._render_draft()
        self._controls()

    def clear(self) -> None:
        self.invalidate()
        for dialog in self.findChildren(EmailSourceDialog):
            dialog.clear_sources()
            dialog.reject()
        for dialog in self.findChildren(EmailEditorDialog):
            for field in dialog.fields.values():
                field.clear()
            dialog.body.clear()
            dialog.reject()
        self.manual_edits = False
        self.workspace = self.draft = None
        self.unsaved = self.editable = self.stale = False
        self.refinement.clear()
        self._refinement_baseline = ""
        self.preview.set_draft(None)
        self.message.clear()
        self._controls()

    def invalidate(self) -> None:
        self.session_epoch = uuid4().hex
        self.pending = None
        self.watchdog.stop()
        self.progress.hide()

    def observe(self, scenario: Scenario) -> None:
        if self.workspace is None or self.stale:
            return
        old = self.workspace.scenario
        changed = (old.id, old.version, old.revision, old.archive_revision) != (
            scenario.id,
            scenario.version,
            scenario.revision,
            scenario.archive_revision,
        )
        if not changed:
            try:
                self.service.check(self.token(), self.workspace, write=False)
            except ApplicationError:
                changed = True
        if changed:
            self.invalidate()
            self.stale = True
            self._state(MaterialState.REVIEW)
            self.message.setText(
                "Сценарій або лист змінено в іншому вікні. Чернетку залишено; "
                "відкрийте актуальну картку."
            )
            self._controls()

    def _render_draft(self) -> None:
        self.preview.set_draft(self.draft)

    def _select_message(self, row: int) -> None:
        self.preview.open_message(row)

    def generate(self) -> None:
        if not self.generate_button.isEnabled() or self.workspace is None:
            return
        if len(self.refinement.toPlainText()) > 2000:
            self.message.setText("Інструкція має містити не більше 2000 символів.")
            return
        if self.manual_edits and not self.confirm_regeneration():
            return
        workspace, previous = self.workspace, self.draft
        scope = self.refinement_scope.currentData()
        token, refinement = self.token(), self.refinement.toPlainText()
        scenario = workspace.scenario
        identity = RequestIdentity(
            uuid4().hex,
            self.session_epoch,
            scenario.id,
            scenario.version,
            scenario.revision,
            scenario.archive_revision,
            workspace.revision,
        )
        signals = WorkerSignals(self)
        signals.finished.connect(self._completed, Qt.ConnectionType.QueuedConnection)
        self._workers[identity.request_id] = signals
        self.pending = identity
        self.progress.show()
        self.message.setText(self.service.provider_label)
        self._state(MaterialState.GENERATING)
        self._controls()
        config = self.service.gateway.config
        # UI delivery deadline; SDK requests retain their gateway timeout/retries.
        deadline = (config.max_retries + 1) * (
            config.parameters.timeout_seconds + config.max_backoff_seconds
        ) * 2 + 10
        self.watchdog.start(int(deadline * 1000))
        service = self.service
        self.pool.start(
            EmailWorker(
                identity,
                signals,
                lambda: service.generate(
                    token,
                    workspace,
                    previous=previous,
                    refinement=refinement,
                    refinement_scope=scope,
                ),
            )
        )

    @Slot(object, object, str)
    def _completed(
        self, identity: RequestIdentity, draft: EmailDraftV2 | None, message: str
    ) -> None:
        signals = self._workers.pop(identity.request_id, None)
        if signals:
            signals.deleteLater()
        if identity != self.pending or identity.session_epoch != self.session_epoch:
            self._controls()
            return
        self.watchdog.stop()
        self.progress.hide()
        self.pending = None
        try:
            self.service.check(self.token(), self.workspace)
        except ApplicationError as error:
            self.stale = True
            message, draft = str(error), None
        if draft is not None:
            self.draft = draft
            self.unsaved = True
            self.manual_edits = False
            self._render_draft()
            self.message.setText(
                "Нова чернетка. Перевірте вміст і явно збережіть лист."
            )
        else:
            self.message.setText(message)
        self._state(
            MaterialState.REVIEW
            if self.stale
            else MaterialState.UNSAVED
            if self.unsaved
            else self.workspace.state
        )
        self._controls()
        # QRunnable may still be returning after emitting its final signal.
        QTimer.singleShot(20, self._controls)

    def _timed_out(self) -> None:
        self.invalidate()
        self.message.setText(
            "Час очікування вичерпано. Доставку результату скасовано; "
            "запит провайдера може ще завершуватися."
        )
        self._state(MaterialState.UNSAVED if self.unsaved else self.workspace.state)
        self._controls()

    def save(self) -> bool:
        if (
            not self.save_button.isEnabled()
            or self.workspace is None
            or self.draft is None
        ):
            return False
        try:
            saved = self.service.save(self.token(), self.workspace, self.draft)
        except ApplicationError as error:
            self.message.setText(str(error))
            return False
        self.workspace, self.draft, self.unsaved = saved, saved.draft, False
        self._refinement_baseline = self.refinement.toPlainText()
        self._state(MaterialState.SAVED)
        self._controls()
        self.saved.emit(saved.scenario)
        return True

    def show_source(self) -> None:
        if self.draft is not None:
            EmailSourceDialog(self.draft, self).exec()

    def edit_message(self) -> None:
        if not self.edit_button.isEnabled() or self.draft is None:
            return
        index = self.preview.selected_index
        if index is None:
            index = max(0, self.messages.currentRow())
        snapshot, epoch, workspace = self.draft, self.session_epoch, self.workspace
        message = [snapshot.slots.main, *snapshot.slots.background][index]

        def apply(value: MessageV1) -> None:
            if (
                epoch != self.session_epoch
                or self.draft is not snapshot
                or self.running
                or self.stale
            ):
                raise ApplicationError(
                    "Чернетку вже змінено. Відкрийте редактор знову."
                )
            candidate = self.service.edit(
                self.token(), workspace, snapshot, index=index, message=value
            )
            self.draft, self.unsaved, self.manual_edits = candidate, True, True
            self._render_draft()
            self.preview.open_message(index)
            self._state(MaterialState.UNSAVED)
            self.message.setText(
                "Ручні правки застосовано локально. Натисніть «Зберегти» для запису."
            )
            self._controls()

        EmailEditorDialog(message, apply, self).exec()

    def confirm_regeneration(self) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("Перегенерація після ручних правок")
        box.setText(
            "AI отримає поточну чернетку з ручними правками. "
            "Створити нового кандидата в обраних межах? "
            "Збережений лист не зміниться; помилка збереже ручні правки."
        )
        box.addButton(QMessageBox.StandardButton.Yes).setText("Перегенерувати")
        box.addButton(QMessageBox.StandardButton.No).setText("Залишити чернетку")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setEscapeButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def ask_unsaved(self) -> QMessageBox.StandardButton:
        box = QMessageBox(self)
        box.setWindowTitle("Незбережений електронний лист")
        box.setText(
            "Залишилися незбережена чернетка або інструкція. "
            "Зберегти лист перед переходом?"
        )
        if self.save_button.isEnabled():
            box.addButton(QMessageBox.StandardButton.Save).setText("Зберегти лист")
        box.addButton(QMessageBox.StandardButton.Discard).setText("Відкинути зміни")
        box.addButton(QMessageBox.StandardButton.Cancel).setText("Залишитися")
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return QMessageBox.StandardButton(box.exec())

    def can_leave(self) -> bool:
        if self.dirty:
            decision = self.ask_unsaved()
            if decision == QMessageBox.StandardButton.Save:
                if not self.save():
                    return False
            elif decision == QMessageBox.StandardButton.Discard:
                self.unsaved = False
                self.refinement.setPlainText(self._refinement_baseline)
            else:
                return False
        self.invalidate()
        return True
