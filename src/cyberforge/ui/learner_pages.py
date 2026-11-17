"""Learner catalog, persisted simulation controller and factual personal history."""

from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.learner_attempts import AttemptEventService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.scenario_integration.contracts import InternalNavigationV1
from cyberforge.ui.email_preview import MailPreview
from cyberforge.ui.preparation_widgets import PreparationStack

STATUS = {
    "IN_PROGRESS": "У процесі",
    "COMPLETED": "Завершено",
    "ABANDONED": "Припинено",
}


def label(text=""):
    item = QLabel(text)
    item.setWordWrap(True)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setMinimumWidth(0)
    return item


def button(text, callback):
    item = QPushButton(text)
    item.setAccessibleName(text)
    item.clicked.connect(callback)
    return item


def stamp(value):
    return value.strftime("%d.%m.%Y %H:%M UTC") if value else "—"


class LearnerActionController:
    """A captured session and request UUID per logical action, never form text."""

    def __init__(self, service, token, attempt):
        self.service, self.token, self.attempt = service, token, attempt
        self.pending = {}
        self.active = True

    def record(self, surface, action, **kwargs):
        if not self.active:
            raise ApplicationError("Сесію проходження закрито.")
        key = (surface, action, kwargs.get("component_id"))
        request, revision = self.pending.setdefault(
            key, (uuid4(), self.attempt.revision)
        )
        self.attempt = self.service.record(
            self.token,
            self.attempt.attempt_id,
            request_id=request,
            expected_revision=revision,
            surface=surface,
            action_id=action,
            **kwargs,
        )
        self.pending.pop(key, None)
        return self.attempt


class LearnerSimulationPage(QWidget):
    exit_requested = Signal()
    changed = Signal()

    def __init__(self, attempts, token_provider):
        super().__init__()
        self.attempts, self.token_provider = attempts, token_provider
        self.events = AttemptEventService(attempts)
        self.controller = None
        self.state = None
        self.browser = None
        self.confirmation = None
        self._restoring = False
        self._display_recorded = False
        layout = QVBoxLayout(self)
        self.heading = label()
        layout.addWidget(self.heading)
        self.notice = label("Це симуляція. Не вводьте справжні облікові дані.")
        layout.addWidget(self.notice)
        self.surfaces = PreparationStack()
        self.mail = MailPreview()
        self.mail.learner_mode = True
        self.mail.message_opened.connect(self._email_opened)
        self.mail.link_requested.connect(self._open_internal)
        self.surfaces.addWidget(self.mail)
        layout.addWidget(self.surfaces, 1)
        self.email_controls = QWidget()
        controls = QGridLayout(self.email_controls)
        controls.setContentsMargins(0, 0, 0, 0)
        self.sender = button(
            "Перевірити відправника", lambda: self._email_action("inspect_sender")
        )
        self.link = button(
            "Перевірити посилання", lambda: self._email_action("inspect_link")
        )
        self.report = button(
            "Повідомити про підозрілий лист", lambda: self._email_action("report")
        )
        self.decline = button("Не переходити за посиланням", self._decline)
        for index, item in enumerate(
            (self.sender, self.link, self.report, self.decline)
        ):
            controls.addWidget(item, index // 2, index % 2)
        layout.addWidget(self.email_controls)
        self.feedback = label()
        layout.addWidget(self.feedback)
        footer = QGridLayout()
        self.footer = footer
        self._footer_columns = 2
        self.complete = button("Завершити сценарій", self._complete)
        self.abandon = button("Припинити проходження", self._abandon)
        self.back = button("До моїх сценаріїв", self.exit_requested.emit)
        footer.addWidget(self.complete, 0, 0)
        footer.addWidget(self.abandon, 0, 1)
        footer.addWidget(self.back, 1, 0, 1, 2)
        layout.addLayout(footer)
        self.setMinimumWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = 3 if self.width() >= 850 else 2
        if columns != self._footer_columns:
            self._footer_columns = columns
            for item in (self.complete, self.abandon, self.back):
                self.footer.removeWidget(item)
            self.footer.addWidget(self.complete, 0, 0)
            self.footer.addWidget(self.abandon, 0, 1)
            if columns == 3:
                self.footer.addWidget(self.back, 0, 2)
            else:
                self.footer.addWidget(self.back, 1, 0, 1, 2)

    def invalidate(self):
        if self.controller:
            self.controller.active = False
        if self.confirmation:
            self.confirmation.close()
            self.confirmation = None
        self.controller, self.state = None, None
        self.mail.set_draft(None)
        self._dispose_browser()
        self.feedback.clear()
        self.heading.clear()
        self._sync_controls()

    def _dispose_browser(self):
        if self.browser is not None:
            self.surfaces.removeWidget(self.browser)
            self.browser.dispose()
            self.browser.deleteLater()
            self.browser = None

    def load(self, attempt_id):
        self.invalidate()
        token = self.token_provider()
        attempt, state = self.attempts.content(token, attempt_id)
        self.controller = LearnerActionController(self.events, token, attempt)
        self.state = state
        self.heading.setText(
            f"{attempt.scenario_name} · версія {attempt.scenario_version}"
        )
        self._restoring = True
        self.mail.set_draft(state.email)
        self.mail.set_link(state.link)
        if attempt.email_opened:
            self.mail.open_message(0)
        self._restoring = False
        if attempt.current_stage == "WEB":
            self._show_web()
        else:
            self.surfaces.setCurrentWidget(self.mail)
        self._sync_controls()

    def _valid(self):
        return bool(
            self.controller
            and self.controller.active
            and self.controller.token == self.token_provider()
        )

    def _perform(self, surface, action, **kwargs):
        if not self._valid():
            return False
        try:
            self.controller.record(surface, action, **kwargs)
        except ApplicationError as error:
            self.feedback.setText(str(error))
            # Hide restricted content as well as refusing writes. Keep history.
            try:
                self.attempts.content(
                    self.controller.token, self.controller.attempt.attempt_id
                )
            except ApplicationError:
                message = str(error)
                self.invalidate()
                self.feedback.setText(message)
            return False
        self.feedback.setText("Дію збережено.")
        self._sync_controls()
        self.changed.emit()
        return True

    def check_access(self):
        if self._valid():
            try:
                self.attempts.content(
                    self.controller.token, self.controller.attempt.attempt_id
                )
            except ApplicationError as error:
                self.invalidate()
                self.feedback.setText(str(error))

    def _sync_controls(self):
        active = self._valid() and self.controller.attempt.status == "IN_PROGRESS"
        email = active and self.controller.attempt.current_stage == "EMAIL"
        self.email_controls.setVisible(bool(email))
        self.mail.setEnabled(bool(email))
        opened = (
            email
            and self.controller.attempt.email_opened
            and self.mail.selected_index == 0
        )
        for item in (self.sender, self.link, self.report, self.decline):
            item.setEnabled(bool(opened))
        self.mail.learner_link.setEnabled(bool(opened))
        self.abandon.setEnabled(bool(active))
        can_complete = active and (
            self.controller.attempt.decision == "DECLINED"
            or self.controller.attempt.web_visited
        )
        self.complete.setEnabled(bool(can_complete))
        if self.browser:
            self.browser.setEnabled(bool(active))
        if self.controller and not active:
            self.feedback.setText(
                "Ви завершили навчальний сценарій."
                if self.controller.attempt.status == "COMPLETED"
                else "Проходження припинено."
            )

    def _email_opened(self, index):
        if self._restoring:
            return
        if index == 0 and not self._perform("email", "email_opened"):
            self.mail.show_inbox()
        self._sync_controls()

    def _email_action(self, action):
        if self._perform("email", action):
            if action == "inspect_sender":
                message = self.state.email.slots.main
                self.feedback.setText(
                    f"Відправник: {message.sender_name} <{message.sender_address}>"
                )
            elif action == "inspect_link":
                self.feedback.setText(
                    "Навчальна адреса: " + self.state.link.display_url
                )

    def _ask(self, text, callback):
        if not self._valid() or self.confirmation:
            return
        controller = self.controller
        box = QMessageBox(
            QMessageBox.Icon.Question,
            "Підтвердження",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        box.button(QMessageBox.StandardButton.Yes).setText("Підтвердити")
        box.button(QMessageBox.StandardButton.No).setText("Повернутися")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        self.confirmation = box

        def finished(result):
            self.confirmation = None
            if self.controller is controller and self._valid():
                if result == QMessageBox.StandardButton.Yes:
                    callback()
                elif self.browser is not None:
                    # Cancelling a leave/completion decision restores the surface;
                    # the factual leave action remains in the append-only log.
                    self.browser.view.show()
            box.deleteLater()

        box.finished.connect(finished)
        box.open()

    def _decline(self):
        if self._perform("transition", "decline"):
            self._complete()

    def _complete(self):
        self._ask(
            "Завершити навчальний сценарій? Оцінку буде обчислено пізніше.",
            lambda: self._perform("system", "completed"),
        )

    def _abandon(self):
        self._ask(
            "Припинити це проходження? Попередні дії залишаться в історії.",
            lambda: self._perform("system", "abandoned"),
        )

    def _open_internal(self):
        if not self._valid():
            return
        a = self.controller.attempt
        navigation = InternalNavigationV1(
            publication_id=a.publication_id,
            scenario_id=a.scenario_id,
            scenario_version=a.scenario_version,
            manifest_digest=a.manifest_digest,
            internal_resource_id=self.state.link.target_resource_id,
        )
        if self._perform(
            "transition",
            "open_internal",
            navigation=navigation,
            source_message_identifier="main",
        ):
            self._show_web()
            self._sync_controls()

    def _show_web(self):
        from cyberforge.ui.web_browser import WebBrowser

        self._dispose_browser()
        self.browser = WebBrowser()
        self.browser.learner_mode = True
        self._display_recorded = False
        controller, browser = self.controller, self.browser

        def loaded():
            if self.controller is controller and self.browser is browser:
                self._web_loaded()

        def interacted(action, component):
            if self.controller is controller and self.browser is browser:
                self._web_action(action, component)

        self.browser.interaction_requested.connect(interacted)
        self.browser.load_succeeded.connect(loaded)
        self.surfaces.addWidget(self.browser)
        self.surfaces.setCurrentWidget(self.browser)
        self.browser.set_draft(self.state.web)

    def _web_loaded(self):
        if not self._display_recorded and self._perform("system", "web_entered"):
            self._display_recorded = True

    def _web_action(self, action, component):
        if not self.browser or not self._display_recorded or self.browser.render_failed:
            return
        if self._perform("web", action, component_id=component):
            self.browser.feedback.setText("Навчальну дію збережено.")
            if action == "leave":
                self.browser.view.hide()
                self._complete()


class LearnerCatalogPage(QWidget):
    def __init__(self, attempts, token_provider):
        super().__init__()
        self.attempts, self.token_provider = attempts, token_provider
        self.rows, self.selected = (), None
        layout = QVBoxLayout(self)
        self.stack = PreparationStack()
        layout.addWidget(self.stack)
        catalog = QWidget()
        catalog_layout = QVBoxLayout(catalog)
        catalog_layout.addWidget(label("Мої сценарії"))
        self.hint = label()
        catalog_layout.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setAccessibleName("Доступні навчальні сценарії")
        self.list.itemActivated.connect(lambda _: self.introduce())
        catalog_layout.addWidget(self.list)
        self.info = button("Переглянути інформацію", self.introduce)
        catalog_layout.addWidget(self.info)
        self.stack.addWidget(catalog)
        introduction = QWidget()
        intro_layout = QVBoxLayout(introduction)
        self.intro = label()
        intro_layout.addWidget(self.intro)
        self.start = button("Розпочати навчання", self.begin)
        intro_layout.addWidget(self.start)
        intro_layout.addWidget(button("До списку сценаріїв", self.show_catalog))
        intro_layout.addStretch()
        self.stack.addWidget(introduction)
        self.simulation = LearnerSimulationPage(attempts, token_provider)
        self.simulation.exit_requested.connect(self.show_catalog)
        self.stack.addWidget(self.simulation)
        self.error = label()
        layout.addWidget(self.error)

    def invalidate(self):
        self.simulation.invalidate()
        self.rows, self.selected = (), None
        self.list.clear()
        self.intro.clear()
        self.error.clear()
        self.stack.setCurrentIndex(0)

    def refresh(self):
        self.simulation.check_access()
        try:
            rows = self.attempts.catalog(self.token_provider())
        except ApplicationError as error:
            self.invalidate()
            self.error.setText(str(error))
            return
        if rows != self.rows:
            selected_id = (
                self.rows[self.list.currentRow()].scenario_id
                if 0 <= self.list.currentRow() < len(self.rows)
                else None
            )
            self.rows = rows
            self.list.clear()
            for index, row in enumerate(rows):
                status = " · У процесі" if row.attempt else ""
                if not row.available:
                    status += " · Доступ обмежено"
                self.list.addItem(f"{row.name}\nВерсія {row.scenario_version}{status}")
                if row.scenario_id == selected_id:
                    self.list.setCurrentRow(index)
            if self.list.currentRow() < 0 and rows:
                self.list.setCurrentRow(0)
        self.hint.setText(
            "Оберіть сценарій, щоб прочитати вступ."
            if rows
            else "Вам поки не призначено навчальних сценаріїв."
        )
        self.info.setEnabled(bool(rows))

    def introduce(self):
        index = self.list.currentRow()
        if not 0 <= index < len(self.rows):
            return
        self.selected = self.rows[index]
        row = self.selected
        self.intro.setText(
            f"{row.name}\nВерсія {row.scenario_version}\n\n"
            "Мета: дослідити навчальний лист і прийняти власне рішення "
            "щодо посилання.\nЦе ізольована симуляція. "
            "Справжні облікові дані вводити не потрібно."
            + (
                (
                    "\n\nДоступ обмежено. Незавершену спробу збережено; зверніться до "
                    "викладача."
                )
                if not row.available
                else ""
            )
        )
        self.start.setText(
            "Продовжити проходження" if row.attempt else "Розпочати навчання"
        )
        self.start.setEnabled(row.available)
        self.stack.setCurrentIndex(1)

    def begin(self):
        if self.selected is None:
            return
        try:
            attempt = self.attempts.start_or_resume(
                self.token_provider(), self.selected.scenario_id
            )
            self.simulation.load(attempt.attempt_id)
        except ApplicationError as error:
            self.error.setText(str(error))
            self.refresh()
            return
        self.error.clear()
        self.stack.setCurrentIndex(2)
        self.refresh()

    def show_catalog(self):
        self.simulation.invalidate()
        self.stack.setCurrentIndex(0)
        self.refresh()


class LearnerHistoryPage(QWidget):
    def __init__(self, attempts, token_provider):
        super().__init__()
        self.attempts, self.token_provider = attempts, token_provider
        self.rows = ()
        layout = QVBoxLayout(self)
        layout.addWidget(label("Мої результати · історія проходжень"))
        layout.addWidget(
            label(
                "Оцінка ще не обчислена. Завершення сценарію не означає успішне "
                "складання."
            )
        )
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setAccessibleName("Мої проходження")
        self.list.currentRowChanged.connect(self.details)
        layout.addWidget(self.list)
        self.detail = label()
        layout.addWidget(self.detail)

    def invalidate(self):
        self.rows = ()
        self.list.clear()
        self.detail.clear()

    def refresh(self):
        try:
            rows = self.attempts.history(self.token_provider())
        except ApplicationError:
            self.invalidate()
            return
        if rows != self.rows:
            self.rows = rows
            self.list.clear()
            for a in rows:
                self.list.addItem(
                    f"{a.scenario_name} · версія {a.scenario_version}\n"
                    f"{STATUS[a.status]} · Початок: {stamp(a.started_at)}\n"
                    f"Завершення: {stamp(a.completed_at or a.abandoned_at)}\n"
                    "Оцінка ще не обчислена"
                )
            if rows:
                self.list.setCurrentRow(0)
        if not rows:
            self.detail.setText("Ви ще не розпочали жодного сценарію.")

    def details(self, index):
        if not 0 <= index < len(self.rows):
            self.detail.clear()
            return
        a = self.rows[index]
        # Refresh ownership through service, never load restricted content here.
        try:
            a = self.attempts.get(self.token_provider(), a.attempt_id)
        except ApplicationError:
            self.invalidate()
            return
        stage = "Лист" if a.current_stage == "EMAIL" else "Навчальний сайт"
        visit = "Так" if a.web_visited else "Ні"
        self.detail.setText(
            f"{a.scenario_name}\n{STATUS[a.status]} · Етап: {stage}\n"
            f"Сайт відвідано: {visit}\nЗбережено подій: {a.last_event_sequence}\n"
            "Оцінка ще не обчислена"
        )
