"""Instructor Web workspace: explicit candidates, shared worker delivery pattern."""

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

from cyberforge.application.email_materials import MaterialState
from cyberforge.application.web_materials import STALE_MESSAGE
from cyberforge.domain.accounts import ApplicationError
from cyberforge.ui.email_worker import EmailWorker, RequestIdentity, WorkerSignals
from cyberforge.ui.pages import label
from cyberforge.ui.web_editor import WebEditorDialog, combo
from cyberforge.ui.web_source import WebSourceDialog
from cyberforge.web.contracts import COMPONENT_LABELS, PRESETS, THEMES


class WebPage(QWidget):
    saved = Signal(object)
    back_requested = Signal()
    state_changed = Signal(object)

    def __init__(self, service, token):
        super().__init__()
        self.service, self.token = service, token
        self.workspace = self.draft = self.pending = None
        self.unsaved = self.editable = self.stale = False
        self.session_epoch = uuid4().hex
        self._workers = {}
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self._timed_out)
        self._refinement_baseline = ""
        self.browser = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(4)
        top = QHBoxLayout()
        self.back_button = QPushButton("← До сценарію")
        self.back_button.clicked.connect(self.back_requested)
        top.addWidget(self.back_button)
        self.title = label("Вебсторінка", "heading")
        top.addWidget(self.title, 1)
        layout.addLayout(top)
        options = QHBoxLayout()
        self.preset, self.theme = combo(PRESETS, "auto"), combo(THEMES, "academic")
        self.preset.setAccessibleName("Стартова композиція")
        self.theme.setAccessibleName("Тема сайту")
        options.addWidget(self.preset)
        options.addWidget(self.theme)
        self.scope = combo(
            {
                "page": "AI: уся сторінка",
                "text": "AI: лише текст",
                "component": "AI: компонент",
            },
            "page",
        )
        options.addWidget(self.scope)
        self.selected_component = QComboBox()
        self.selected_component.setMinimumContentsLength(10)
        self.selected_component.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.selected_component.setAccessibleName("Компонент для AI refinement")
        options.addWidget(self.selected_component, 1)
        # Four adjacent native combos must fit a 768px workspace. Segoe UI on
        # Windows can expand the ten-character hints beyond that workspace.
        # Keep full choices in the popup while allowing the closed controls to
        # shrink; the selected-component control receives remaining width.
        for control in (self.preset, self.theme, self.scope, self.selected_component):
            control.setMinimumContentsLength(6)
        layout.addLayout(options)
        info = QHBoxLayout()
        self.provider = label(service.provider_label)
        self.status = label(MaterialState.EMPTY)
        info.addWidget(self.provider, 2)
        info.addWidget(self.status, 1)
        layout.addLayout(info)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(5)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.preview_row = QHBoxLayout()
        self.preview_row.addStretch(1)
        self.placeholder = label("Збережіть лист і згенеруйте сайт.")
        self.preview_row.addWidget(self.placeholder, 18)
        self.preview_row.addStretch(1)
        layout.addLayout(self.preview_row, 1)
        self.message = label("")
        layout.addWidget(self.message)
        self.refinement = QPlainTextEdit()
        self.refinement.setFixedHeight(42)
        self.refinement.setTabChangesFocus(True)
        self.refinement.setAccessibleName("Уточнення викладача, до 2000 символів")
        self.refinement.setPlaceholderText(
            "Уточнення для AI. Ручні зміни — «Редагувати сайт»."
        )
        layout.addWidget(self.refinement)
        actions = QHBoxLayout()
        self.code_button = QPushButton("Переглянути код")
        self.edit_button = QPushButton("Редагувати сайт")
        self.generate_button = QPushButton("Згенерувати")
        self.save_button = QPushButton("Зберегти")
        self.save_button.setObjectName("primary")
        for button, slot in (
            (self.code_button, self.show_source),
            (self.edit_button, self.edit),
            (self.generate_button, self.generate),
            (self.save_button, self.save),
        ):
            button.setStyleSheet("padding:6px 10px")
            button.clicked.connect(slot)
            if button is self.edit_button:
                top.addWidget(button)
            else:
                actions.addWidget(button)
        layout.addLayout(actions)
        for field in (self.title, self.provider, self.status, self.message):
            policy = field.sizePolicy()
            policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)
            policy.setHeightForWidth(field.wordWrap())
            field.setSizePolicy(policy)
        self._controls()

    @property
    def running(self):
        return bool(self._workers) or self.pool.activeThreadCount() > 0

    @property
    def dirty(self):
        return self.workspace is not None and (
            self.unsaved or self.refinement.toPlainText() != self._refinement_baseline
        )

    def _state(self, state):
        self.status.setText(state)
        self.state_changed.emit(state)

    def _controls(self):
        writable = self.workspace is not None and self.editable and not self.stale
        self.generate_button.setEnabled(
            writable
            and self.service.available
            and not self.running
            and self.workspace.email is not None
        )
        self.generate_button.setText("Перегенерувати" if self.draft else "Згенерувати")
        fresh = (
            self.workspace is not None and self.workspace.state != MaterialState.REVIEW
        )
        self.save_button.setEnabled(
            writable and self.unsaved and self.pending is None and fresh
        )
        self.edit_button.setEnabled(
            writable and fresh and self.draft is not None and not self.running
        )
        self.code_button.setEnabled(self.draft is not None)
        for control in (self.preset, self.theme, self.scope, self.selected_component):
            control.setEnabled(writable and not self.running)
        self.refinement.setReadOnly(not writable or self.running)

    def _render(self):
        if self.browser is None and self.draft is not None:
            from cyberforge.ui.web_browser import WebBrowser

            self.browser = WebBrowser(self)
            self.preview_row.replaceWidget(self.placeholder, self.browser)
            self.placeholder.hide()
        if self.browser is not None:
            self.browser.set_draft(self.draft)
        selected = self.selected_component.currentData()
        self.selected_component.clear()
        if self.draft:
            for c in self.draft.page.components:
                self.selected_component.addItem(
                    f"{COMPONENT_LABELS[c.type]} · {c.id}", c.id
                )
            self.selected_component.setCurrentIndex(
                max(0, self.selected_component.findData(selected))
            )

    def open(self, scenario, *, editable):
        workspace = self.service.load(self.token(), scenario)
        self.clear()
        self.workspace, self.draft = workspace, workspace.draft
        self.editable = (
            editable and not scenario.archived and scenario.status == "draft"
        )
        self.title.setText(f"{scenario.name} · Сайт · v{scenario.version}")
        if self.draft:
            self.preset.setCurrentIndex(self.preset.findData(self.draft.preset))
            self.theme.setCurrentIndex(self.theme.findData(self.draft.page.theme))
        else:
            self.preset.setCurrentIndex(0)
            self.theme.setCurrentIndex(0)
        self._state(workspace.state)
        if workspace.state == MaterialState.REVIEW:
            self.message.setText(STALE_MESSAGE)
        elif workspace.email is None:
            self.message.setText(
                "Спочатку збережіть валідний лист цієї версії сценарію."
            )
        self._render()
        self._controls()

    def invalidate(self):
        self.session_epoch = uuid4().hex
        self.pending = None
        self.watchdog.stop()
        self.progress.hide()

    def clear(self):
        self.invalidate()
        for kind in (WebEditorDialog, WebSourceDialog):
            for dialog in self.findChildren(kind):
                dialog.clear_sources()
                dialog.reject()
        self.workspace = self.draft = None
        self.unsaved = self.editable = self.stale = False
        self.refinement.clear()
        self._refinement_baseline = ""
        self.message.clear()
        self._render()
        self._controls()

    def observe(self, scenario):
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
            self.message.setText(STALE_MESSAGE)
            self._state(MaterialState.REVIEW)
            self._controls()

    def generate(self):
        if not self.generate_button.isEnabled():
            return
        refinement = self.refinement.toPlainText()
        if len(refinement) > 2000:
            self.message.setText("Інструкція має містити не більше 2000 символів.")
            return
        workspace, previous = self.workspace, self.draft
        stale = workspace.state == MaterialState.REVIEW
        if stale:
            previous = None
        scope = self.scope.currentData() if previous else "page"
        token = self.token()
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
        options = dict(
            previous=previous,
            refinement=refinement,
            refinement_scope=scope,
            selected_component=self.selected_component.currentData(),
            preset=self.preset.currentData(),
            theme=self.theme.currentData(),
        )
        signals = WorkerSignals(self)
        signals.finished.connect(self._completed, Qt.ConnectionType.QueuedConnection)
        self._workers[identity.request_id] = signals
        self.pending = identity
        self.progress.show()
        self._state(MaterialState.GENERATING)
        self._controls()
        config = self.service.gateway.config
        deadline = (config.max_retries + 1) * (
            config.parameters.timeout_seconds + config.max_backoff_seconds
        ) * 2 + 10
        self.watchdog.start(int(deadline * 1000))
        service = self.service
        self.pool.start(
            EmailWorker(
                identity, signals, lambda: service.generate(token, workspace, **options)
            )
        )

    @Slot(object, object, str)
    def _completed(self, identity, draft, message):
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
            # New generation explicitly supersedes stale saved source only locally.
            from dataclasses import replace

            self.workspace = replace(self.workspace, state=MaterialState.UNSAVED)
            self.draft, self.unsaved = draft, True
            self._render()
            self.message.setText("Нова чернетка сайту. Перевірте та явно збережіть її.")
        else:
            self.message.setText(message.replace("лист", "сайт"))
        self._state(
            MaterialState.REVIEW
            if self.stale
            else MaterialState.UNSAVED
            if self.unsaved
            else self.workspace.state
        )
        self._controls()
        QTimer.singleShot(20, self._controls)

    def _timed_out(self):
        self.invalidate()
        self.message.setText(
            "Час очікування вичерпано. Чернетку залишено; запит ще виконується."
        )
        self._state(MaterialState.UNSAVED if self.unsaved else self.workspace.state)
        self._controls()

    def save(self):
        if not self.save_button.isEnabled():
            return False
        try:
            workspace = self.service.save(self.token(), self.workspace, self.draft)
        except ApplicationError as error:
            self.message.setText(str(error))
            return False
        self.workspace, self.draft, self.unsaved = workspace, workspace.draft, False
        self._refinement_baseline = self.refinement.toPlainText()
        self._state(MaterialState.SAVED)
        self._controls()
        self.saved.emit(workspace.scenario)
        return True

    def edit(self):
        if not self.edit_button.isEnabled():
            return
        snapshot, epoch, workspace = self.draft, self.session_epoch, self.workspace

        def apply(page):
            if (
                epoch != self.session_epoch
                or self.draft is not snapshot
                or self.running
                or self.stale
            ):
                raise ApplicationError("Чернетка змінилася. Відкрийте редактор знову.")
            self.draft = self.service.edit(self.token(), workspace, snapshot, page)
            self.unsaved = True
            self.theme.setCurrentIndex(self.theme.findData(page.theme))
            self._render()
            self._state(MaterialState.UNSAVED)
            self._controls()

        WebEditorDialog(snapshot.page, apply, self).exec()

    def show_source(self):
        if self.draft is not None and self.browser is not None:
            WebSourceDialog(self.draft, self.browser.rendered, self).exec()

    def ask_unsaved(self):
        box = QMessageBox(self)
        box.setWindowTitle("Незбережений сайт")
        box.setText("Зберегти чернетку сайту перед переходом?")
        if self.save_button.isEnabled():
            box.addButton(QMessageBox.StandardButton.Save).setText("Зберегти сайт")
        box.addButton(QMessageBox.StandardButton.Discard).setText("Відкинути зміни")
        box.addButton(QMessageBox.StandardButton.Cancel).setText("Залишитися")
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return QMessageBox.StandardButton(box.exec())

    def can_leave(self):
        if self.dirty:
            decision = self.ask_unsaved()
            if decision == QMessageBox.StandardButton.Save:
                if not self.save():
                    return False
            elif decision == QMessageBox.StandardButton.Discard:
                self.unsaved = False
                self.draft = self.workspace.draft
                self.refinement.setPlainText(self._refinement_baseline)
                self._render()
            else:
                return False
        self.invalidate()
        return True
