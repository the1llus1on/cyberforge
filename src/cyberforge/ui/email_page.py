"""Email Constructor: native plain-text mail template, explicit saves and workers."""

from collections.abc import Callable
from uuid import uuid4

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.application.email_materials import (
    EmailMaterialService,
    EmailWorkspace,
    MaterialState,
)
from cyberforge.domain.accounts import ApplicationError
from cyberforge.domain.scenarios import Scenario
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
        self.read_messages: set[int] = set()
        self._refinement_baseline = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        top = QHBoxLayout()
        self.back_button = QPushButton("← До картки сценарію")
        self.back_button.clicked.connect(self.back_requested)
        top.addWidget(self.back_button)
        self.title = label("Електронний лист", "heading")
        top.addWidget(self.title, 1)
        layout.addLayout(top)
        self.provider = label(service.provider_label)
        layout.addWidget(self.provider)
        layout.addWidget(
            label("Використовуйте лише синтетичні дані та навчальні організації.")
        )
        self.status = label(MaterialState.EMPTY)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setAccessibleName("Триває генерація листа")
        self.progress.hide()
        layout.addWidget(self.progress)
        # 1:18:1 = approximately 90 percent of the central content width.
        preview_row = QHBoxLayout()
        preview_row.setContentsMargins(0, 0, 0, 0)
        preview_row.addStretch(1)
        self.preview = QFrame()
        self.preview.setObjectName("emailPreview")
        self.preview.setStyleSheet(
            "QFrame#emailPreview { background: #20232a; border: 1px solid #343843; "
            "border-radius: 12px; } QListWidget::item { padding: 9px; }"
        )
        mail = QVBoxLayout(self.preview)
        mail.addWidget(label("ПОШТА / Вхідні · навчальний перегляд", "eyebrow"))
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.messages = QListWidget()
        self.messages.setMinimumSize(0, 110)
        self.messages.setAccessibleName("Вхідні синтетичні листи")
        self.messages.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.messages.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.messages.currentRowChanged.connect(self._select_message)
        self.splitter.addWidget(self.messages)
        detail_widget = QWidget()
        detail_widget.setMinimumWidth(0)
        detail = QVBoxLayout(detail_widget)
        self.subject = self._header("Тема вибраного листа")
        self.subject.setPlainText("Листа ще немає")
        self.subject.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none; "
            "font-size: 18px; font-weight: 600; }"
        )
        self.sender = self._header("Відправник і адреса вибраного листа")
        self.timestamp = label("")
        self.body = QPlainTextEdit()
        self.body.setReadOnly(True)
        self.body.setTabChangesFocus(True)
        self.body.setMinimumSize(0, 150)
        self.body.setAccessibleName("Текст вибраного листа")
        self.body.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        for widget in (self.subject, self.sender, self.timestamp, self.body):
            detail.addWidget(widget)
        self.resource = label("")
        self.resource.setMinimumHeight(
            self.resource.fontMetrics().lineSpacing() * 2 + 4
        )
        detail.addWidget(self.resource)
        self.splitter.addWidget(detail_widget)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        mail.addWidget(self.splitter, 1)
        preview_row.addWidget(self.preview, 18)
        preview_row.addStretch(1)
        layout.addLayout(preview_row, 1)
        self.message = label("")
        layout.addWidget(self.message)
        layout.addWidget(label("Уточнення викладача (до 2000 символів)"))
        self.refinement = QPlainTextEdit()
        self.refinement.setAccessibleName("Інструкція уточнення листа")
        self.refinement.setPlaceholderText(
            "Наприклад: зроби текст коротшим і додай пояснення дії"
        )
        self.refinement.setFixedHeight(72)
        self.refinement.setTabChangesFocus(True)
        self.refinement.textChanged.connect(self._controls)
        layout.addWidget(self.refinement)
        actions = QHBoxLayout()
        self.code_button = QPushButton("Переглянути код")
        self.code_button.clicked.connect(self.show_source)
        self.generate_button = QPushButton("Згенерувати")
        self.generate_button.clicked.connect(self.generate)
        self.save_button = QPushButton("Зберегти")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        for control in (self.code_button, self.generate_button, self.save_button):
            actions.addWidget(control)
        layout.addLayout(actions)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._controls()

    @staticmethod
    def _header(name: str) -> QPlainTextEdit:
        # QLabel cannot wrap long unbroken subjects/addresses. Keep all validated
        # header text reachable without letting its size hint expand the inbox.
        header = QPlainTextEdit()
        header.setReadOnly(True)
        header.setTabChangesFocus(True)
        header.setAccessibleName(name)
        header.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        header.setStyleSheet(
            "QPlainTextEdit { background: transparent; border: none; }"
        )
        header.setFixedHeight(54)
        header.setMinimumWidth(0)
        return header

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        vertical = self.width() < 850
        self.splitter.setOrientation(
            Qt.Orientation.Vertical if vertical else Qt.Orientation.Horizontal
        )
        self.messages.setMaximumHeight(145 if vertical else 16777215)

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
        self.generate_button.setEnabled(
            writable and self.service.available and not self.running
        )
        self.save_button.setEnabled(writable and self.unsaved and self.pending is None)
        self.code_button.setEnabled(self.draft is not None)
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
            dialog.source.clear()
            dialog.reject()
        self.workspace = self.draft = None
        self.unsaved = self.editable = self.stale = False
        self.refinement.clear()
        self._refinement_baseline = ""
        self.messages.clear()
        self.subject.setPlainText("Листа ще немає")
        self.sender.clear()
        self.timestamp.clear()
        self.body.clear()
        self.resource.clear()
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
        self.messages.clear()
        self.read_messages.clear()
        if self.draft is None:
            return
        for index, message in enumerate(
            [self.draft.slots.main, *self.draft.slots.background]
        ):
            item = QListWidgetItem(
                f"● {message.sender_name}\n{message.subject}\n"
                f"{message.body_text[:100].replace(chr(10), ' ')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.messages.addItem(item)
        self.messages.setCurrentRow(0)

    def _select_message(self, row: int) -> None:
        if self.draft is None or row < 0:
            return
        messages = [self.draft.slots.main, *self.draft.slots.background]
        if row >= len(messages):
            return
        message = messages[row]
        self.read_messages.add(row)
        item = self.messages.item(row)
        font = item.font()
        font.setBold(False)
        item.setFont(font)
        item.setText(item.text().replace("● ", "✓ ", 1))
        self.subject.setPlainText(message.subject)
        self.sender.setPlainText(f"{message.sender_name}\n{message.sender_address}")
        # Template-only synthetic time, never a real delivery date or AI claim.
        minutes = 9 * 60 + 30 - row * 5
        self.timestamp.setText(
            f"{minutes // 60:02d}:{minutes % 60:02d} · навчальний час"
        )
        self.body.setPlainText(message.body_text)
        self.resource.setText(
            f"Навчальне посилання: {self.draft.slots.internal_resource_id}\n"
            "Перехід до Web буде доступний на наступному етапі."
            if row == 0
            else "Фоновий синтетичний лист"
        )

    def generate(self) -> None:
        if not self.generate_button.isEnabled() or self.workspace is None:
            return
        if len(self.refinement.toPlainText()) > 2000:
            self.message.setText("Інструкція має містити не більше 2000 символів.")
            return
        workspace, previous = self.workspace, self.draft
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
                    token, workspace, previous=previous, refinement=refinement
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
            self._render_draft()
            self.message.setText(
                "Перевірте нову чернетку. Заявлені ознаки NIST ще не підтверджені. "
                "Збереження — лише явно."
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
