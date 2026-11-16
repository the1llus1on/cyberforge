"""Instructor integration workspace; explicit saves and publication confirmation."""

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import ScenarioPublicationService
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.groups.service import GroupService
from cyberforge.scenario_integration.contracts import CRITERIA, criterion
from cyberforge.ui.email_preview import MailPreview
from cyberforge.ui.pages import label

APPLICABILITY = {
    "all_attempts": "Усі шляхи",
    "web_visited": "Лише після відвідування Web",
    "web_not_visited": "Web не відвідано",
}


class IntegrationDialog(QDialog):
    def __init__(
        self,
        integration: ScenarioIntegrationService,
        token,
        expected,
        *,
        owned,
        parent=None,
    ):
        super().__init__(parent)
        self.integration, self.token, self.expected = integration, token, expected
        self.readiness = ScenarioReadinessService(integration)
        self.publications = ScenarioPublicationService(self.readiness)
        self.session_token = token()
        self.owned, self.changed, self.forced = owned, False, False
        self.browser = None
        self.report = None
        self._loading = True
        self.setWindowTitle("Інтеграція та публікація сценарію")
        self.resize(760, 620)
        self.setMinimumSize(520, 440)
        outer = QVBoxLayout(self)
        self.identity = label("")
        outer.addWidget(self.identity)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        self.link_label = QLineEdit()
        self.link_label.setMaxLength(200)
        self.display_url = QLineEdit()
        self.display_url.setMaxLength(512)
        self.target = QComboBox()
        self.target.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.target.setMinimumContentsLength(10)
        link_form = QFormLayout()
        link_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        link_form.addRow(
            label(
                "Зв’язок main Email → поточний збережений Web. Адреса лише для "
                "показу; перехід у preview вимкнено."
            )
        )
        link_form.addRow("Видима назва посилання", self.link_label)
        link_form.addRow("Видима HTTPS адреса Email", self.display_url)
        link_form.addRow("Дозволена внутрішня ціль", self.target)
        self.web_address = label("")
        link_form.addRow(self.web_address)
        self.save_link_button = QPushButton("Зберегти зв’язок")
        self.save_link_button.clicked.connect(self.save_link)
        link_form.addRow(self.save_link_button)
        self._scroll_tab(link_form, "Зв’язок Email → Web")
        rubric_layout = QVBoxLayout()
        rubric_layout.addWidget(
            label(
                "Рубрика оцінювання · визначення без обчислення оцінок. "
                "Позначте критерії, задайте додатні ваги й застосовність. "
                "Порожній редактор не є схваленою рубрикою."
            )
        )
        self.criteria = {}
        for spec in CRITERIA:
            content = QWidget()
            form = QFormLayout(content)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            enabled = QCheckBox(spec.label)
            enabled.setToolTip(spec.description)
            weight = QLineEdit("1.0")
            weight.setMaxLength(32)
            weight.setAccessibleName("Додатна вага критерію")
            applicability = QComboBox()
            for value in spec.applicability:
                applicability.addItem(APPLICABILITY[value], value)
            form.addRow(enabled)
            row = QHBoxLayout()
            row.addWidget(label("Вага"))
            row.addWidget(weight)
            form.addRow(row)
            form.addRow("Застосовність", applicability)
            form.addRow(
                label(
                    spec.description + "\nEvidence/actions: " + ", ".join(spec.actions)
                )
            )
            rubric_layout.addWidget(content)
            self.criteria[spec.id] = enabled, weight, applicability
        self.save_rubric_button = QPushButton("Зберегти рубрику")
        self.save_rubric_button.clicked.connect(self.save_rubric)
        rubric_layout.addWidget(self.save_rubric_button)
        self._scroll_tab(rubric_layout, "Рубрика оцінювання")
        self.mail = MailPreview()
        self.tabs.addTab(self.mail, "Email preview")
        self.web_tab = QWidget()
        self.web_layout = QVBoxLayout(self.web_tab)
        self.web_placeholder = label(
            "Відкрийте цю вкладку для перегляду збереженого сайту."
        )
        self.web_layout.addWidget(self.web_placeholder)
        self.tabs.addTab(self.web_tab, "Web preview")
        review_layout = QVBoxLayout()
        self.review_summary = label("")
        review_layout.addWidget(self.review_summary)
        review_layout.addWidget(label("Навчальні групи"))
        self.groups = QListWidget()
        self.groups.setMinimumHeight(90)
        self.groups.setMaximumHeight(130)
        review_layout.addWidget(self.groups)
        self.check_button = QPushButton("Перевірити готовність")
        self.check_button.clicked.connect(self.check_readiness)
        review_layout.addWidget(self.check_button)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(100)
        review_layout.addWidget(self.details)
        self.ack = QCheckBox("Підтверджую зміст і всі попередження")
        self.ack.setToolTip(
            "Підтвердження стосується точних збережених ревізій і вибраних груп."
        )
        review_layout.addWidget(self.ack)
        review_layout.addWidget(
            label(
                "Опублікований вміст незмінний. Подальші правки потребують "
                "нової версії. Оцінки зараз не обчислюються."
            )
        )
        self.publish_button = QPushButton("Публікувати сценарій")
        self.publish_button.setObjectName("primary")
        self.publish_button.clicked.connect(self.publish)
        review_layout.addWidget(self.publish_button)
        self._scroll_tab(review_layout, "Готовність і публікація")
        history_layout = QVBoxLayout()
        history_layout.addWidget(
            label(
                "Історичні публікації та керування доступом. Grant/revoke "
                "змінює лише доступ; вміст і manifest залишаються незмінними."
            )
        )
        self.history = QComboBox()
        history_layout.addWidget(self.history)
        self.open_history = QPushButton("Переглянути цю опубліковану версію")
        self.open_history.clicked.connect(self.load_history)
        history_layout.addWidget(self.open_history)
        self.grant_groups = QListWidget()
        self.grant_groups.setMinimumHeight(90)
        history_layout.addWidget(self.grant_groups)
        self.available_group = QComboBox()
        self.available_group.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.available_group.setMinimumContentsLength(10)
        history_layout.addWidget(self.available_group)
        self.add_grant = QPushButton("Надати доступ групі")
        self.revoke_grant = QPushButton("Відкликати вибраний доступ")
        self.add_grant.clicked.connect(lambda: self.change_grant(True))
        self.revoke_grant.clicked.connect(lambda: self.change_grant(False))
        history_layout.addWidget(self.add_grant)
        history_layout.addWidget(self.revoke_grant)
        self.audit_text = QPlainTextEdit()
        self.audit_text.setReadOnly(True)
        self.audit_text.setMinimumHeight(110)
        history_layout.addWidget(self.audit_text)
        self._scroll_tab(history_layout, "Історія та доступ")
        self.message = label("")
        outer.addWidget(self.message)
        self.close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.close_buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            "Закрити"
        )
        self.close_buttons.rejected.connect(self.reject)
        outer.addWidget(self.close_buttons)
        self.groups.itemChanged.connect(self.invalidate_review)
        self.history.currentIndexChanged.connect(self.load_history)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.load()
        self._loading = False

    def _scroll_tab(self, layout, title):
        body = QWidget()
        body.setLayout(layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self.tabs.addTab(scroll, title)

    def _authorized(self):
        if self.token() != self.session_token:
            raise ApplicationError("Сесію змінено. Відкрийте сценарій повторно.")
        self.integration.accounts.current(self.session_token)

    def link_values(self):
        return (
            self.link_label.text(),
            self.display_url.text(),
            self.target.currentData(),
        )

    def rubric_values(self):
        return tuple(
            (key, enabled.isChecked(), weight.text(), app.currentData())
            for key, (enabled, weight, app) in self.criteria.items()
        )

    @property
    def dirty(self):
        return (
            not self._loading
            and self.writable
            and (
                self.link_values() != self._link_baseline
                or self.rubric_values() != self._rubric_baseline
            )
        )

    def load(self):
        self._authorized()
        self.state = self.integration.inspect(self.session_token, self.expected)
        self.writable = (
            self.owned
            and not self.expected.archived
            and self.expected.status == "draft"
        )
        self.identity.setText(
            f"Сценарій {self.expected.id} · v{self.expected.version} · "
            f"ревізія {self.expected.revision} · {self.expected.status.label}"
        )
        link = self.state.link
        self.link_label.setText(
            link.link_label if link else "Переглянути навчальний матеріал"
        )
        self.display_url.setText(
            link.display_url
            if link
            else (self.state.web.page.display_url if self.state.web else "")
        )
        self.target.clear()
        if self.state.web:
            resource = self.state.web.page.internal_resource_id
            self.target.addItem(resource, resource)
        self.web_address.setText(
            "Адреса Web (лише показ): "
            + (
                self.state.web.page.display_url
                if self.state.web
                else "Web не збережено"
            )
        )
        self._link_baseline = self.link_values()
        saved = (
            {c.criterion_id: c for c in self.state.rubric.criteria}
            if self.state.rubric
            else {}
        )
        for key, (enabled, weight, app) in self.criteria.items():
            entry = saved.get(key)
            enabled.setChecked(entry is not None)
            weight.setText(str(entry.weight) if entry else "1.0")
            app.setCurrentIndex(app.findData(entry.applicability) if entry else 0)
            for widget in (enabled, weight, app):
                widget.setEnabled(self.writable)
        self._rubric_baseline = self.rubric_values()
        self.save_link_button.setEnabled(self.writable and self.state.web is not None)
        self.save_rubric_button.setEnabled(self.writable)
        self.link_label.setReadOnly(not self.writable)
        self.display_url.setReadOnly(not self.writable)
        self.target.setEnabled(self.writable)
        self.mail.set_draft(self.state.email)
        self.mail.set_link(self.state.link)
        if self.state.email:
            self.mail.open_message(0)
        if self.browser:
            self.browser.set_draft(self.state.web)
        self._loading = True
        self.groups.clear()
        self.available_group.clear()
        for group in GroupService(self.integration.accounts).list_groups(
            self.session_token
        ):
            item = QListWidgetItem(group.name)
            item.setData(Qt.ItemDataRole.UserRole, group.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.groups.addItem(item)
            self.available_group.addItem(group.name, group.id)
        self.groups.setEnabled(self.writable)
        self._loading = False
        self.check_readiness()
        # Rebuild without temporarily targeting the first (latest) publication.
        # Expected version is the content currently displayed, even after reopen.
        with QSignalBlocker(self.history):
            self.history.clear()
            selected = -1
            for publication in self.publications.history(
                self.session_token, self.expected.id
            ):
                self.history.addItem(
                    f"v{publication.manifest.snapshot.scenario_version} · "
                    f"публікація {publication.id}",
                    publication.id,
                )
                if (
                    publication.manifest.snapshot.scenario_version
                    == self.expected.version
                ):
                    selected = self.history.count() - 1
            # A draft has no publication target until an instructor selects one.
            self.history.setCurrentIndex(selected)
        self.refresh_grants()

    def _reload_state(self):
        self.state = self.integration.inspect(self.session_token, self.expected)
        self.mail.set_draft(self.state.email)
        self.mail.set_link(self.state.link)
        if self.state.email:
            self.mail.open_message(0)
        self.invalidate_review()

    def save_link(self):
        try:
            self._authorized()
            self.integration.save_link(
                self.session_token,
                self.expected,
                link_label=self.link_label.text(),
                display_url=self.display_url.text(),
                target_resource_id=self.target.currentData(),
                expected_revision=self.state.checked_sources["link_revision"] or 0,
                expected_email_revision=self.state.checked_sources["email_revision"],
                expected_web_revision=self.state.checked_sources["web_revision"],
            )
            self._link_baseline = self.link_values()
            self.changed = True
            self._reload_state()
            self.message.setText("Зв’язок збережено. Вміст Email/Web не змінено.")
            return True
        except ApplicationError as error:
            self.message.setText(str(error))
            return False

    def save_rubric(self):
        try:
            self._authorized()
            selected = tuple(
                criterion(key, float(weight.text()), app.currentData())
                for key, (enabled, weight, app) in self.criteria.items()
                if enabled.isChecked()
            )
            self.integration.save_rubric(
                self.session_token,
                self.expected,
                selected,
                expected_revision=self.state.checked_sources["rubric_revision"] or 0,
            )
            self._rubric_baseline = self.rubric_values()
            self.changed = True
            self._reload_state()
            self.message.setText("Рубрику збережено. Оцінки не обчислювалися.")
            return True
        except (ValueError, TypeError):
            self.message.setText(
                "Вага має бути додатним скінченним числом до 10000; "
                "перевірте всі вибрані критерії."
            )
            return False
        except ApplicationError as error:
            self.message.setText(str(error))
            return False

    def selected_groups(self):
        return tuple(
            self.groups.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.groups.count())
            if self.groups.item(i).checkState() == Qt.CheckState.Checked
        )

    def invalidate_review(self, *args):
        self.report = None
        self.ack.setChecked(False)
        self.publish_button.setEnabled(False)
        if not self._loading:
            self.check_readiness()

    def check_readiness(self):
        try:
            self._authorized()
            self.report = self.readiness.evaluate(
                self.session_token,
                self.expected,
                selected_group_ids=self.selected_groups(),
            )
            current_state = self.integration.inspect(self.session_token, self.expected)
            if (
                self.report.snapshot != self.state.snapshot
                or current_state.checked_sources != self.state.checked_sources
            ):
                self.report = None
                raise ApplicationError(
                    "Матеріали змінилися після відкриття огляду. Збережіть "
                    "власні правки окремо й повторно відкрийте сценарій."
                )
            self.ack.setChecked(False)
            self.details.setPlainText(
                "\n\n".join(
                    f"{c.status} · {c.check_id}\n{c.explanation}\nДія: {c.correction}"
                    for c in self.report.checks
                )
            )
            snapshot = self.report.snapshot
            self.review_summary.setText(
                (
                    "Технічно готово. Потрібне підтвердження."
                    if self.report.technical_ready
                    else "Публікацію заблоковано."
                )
                + (
                    f"\nEmail r{snapshot.email_revision} · "
                    f"Web r{snapshot.web_revision} · "
                    f"Link r{snapshot.link_revision} · "
                    f"Rubric r{snapshot.rubric_revision}"
                    if snapshot
                    else ""
                )
                + "\nРубрика: "
                + str(len(self.state.rubric.criteria) if self.state.rubric else 0)
                + " критеріїв."
            )
            self.publish_button.setEnabled(
                self.writable and self._publication_inputs_ready(self.report)
            )
            self.message.clear()
        except ApplicationError as error:
            self.message.setText(str(error))
            self.publish_button.setEnabled(False)
            self.report = None

    @staticmethod
    def _publication_inputs_ready(report):
        return (
            report.technical_ready
            and bool(report.selected_group_ids)
            and not any(
                c.status == "BLOCKED" and c.check_id != "instructor_confirmation"
                for c in report.checks
            )
        )

    def final_confirmation(self):
        groups = [
            self.groups.item(i).text()
            for i in range(self.groups.count())
            if self.groups.item(i).checkState() == Qt.CheckState.Checked
        ]
        return (
            QMessageBox.question(
                self,
                "Підтвердити публікацію",
                f"Сценарій {self.expected.id}, версія {self.expected.version}\n"
                + "Групи: "
                + ", ".join(groups)
                + "\nОпублікований вміст стане незмінним. Підтвердити?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            == QMessageBox.StandardButton.Yes
        )

    def publish(self):
        try:
            self._authorized()
            if self.dirty:
                raise ApplicationError(
                    "Спочатку збережіть або відкиньте правки зв’язку та рубрики."
                )
            report = self.report
            # Recheck current assignments before opening the final dialog. The
            # service still repeats this inside its write transaction afterwards.
            current = self.readiness.evaluate(
                self.session_token,
                self.expected,
                selected_group_ids=self.selected_groups(),
            )
            if not self._publication_inputs_ready(current):
                self.publish_button.setEnabled(False)
                raise ApplicationError(
                    "Публікацію заблоковано: оберіть дозволені навчальні групи "
                    "та усуньте блокувальні помилки."
                )
            if (
                report is not None
                and current.review_fingerprint != report.review_fingerprint
            ):
                raise ApplicationError(
                    "Дані огляду змінилися. Перевірте готовність повторно."
                )
            if report is None or not self.ack.isChecked():
                raise ApplicationError(
                    "Перевірте готовність і явно підтвердьте зміст та попередження."
                )
            if not self.final_confirmation():
                return False
            self._authorized()
            receipt = self.readiness.confirm(
                self.session_token,
                self.expected,
                review_fingerprint=report.review_fingerprint,
                selected_group_ids=self.selected_groups(),
                acknowledged_warnings=report.acknowledgement_requirements,
                semantic_review=True,
            )
            self.publications.publish(
                self.session_token,
                self.expected,
                confirmation_id=receipt.confirmation_id,
            )
            self.changed = True
            self.expected = self.integration.scenarios.get(
                self.session_token, self.expected.id, version=self.expected.version
            )
            self.load()
            self.message.setText(
                "Сценарій опубліковано. Вміст доступний лише для читання."
            )
            return True
        except ApplicationError as error:
            self.publish_button.setEnabled(False)
            self.message.setText(str(error))
            return False

    def _selected_publication(self):
        publication = next(
            (
                p
                for p in self.publications.history(self.session_token, self.expected.id)
                if p.id == self.history.currentData()
            ),
            None,
        )
        if publication is None or (
            publication.manifest.snapshot.scenario_id != self.expected.id
            or publication.manifest.snapshot.scenario_version != self.expected.version
        ):
            raise ApplicationError(
                "Вибрана публікація не відповідає відкритій версії. "
                "Повторно відкрийте потрібну публікацію."
            )
        return publication

    def refresh_grants(self, *args):
        self.grant_groups.clear()
        self.audit_text.clear()
        publication_id = self.history.currentData()
        self.add_grant.setEnabled(False)
        self.revoke_grant.setEnabled(False)
        if publication_id is None:
            return
        try:
            self._authorized()
            self._selected_publication()
            self.add_grant.setEnabled(self.owned)
            self.revoke_grant.setEnabled(self.owned)
            for grant in self.publications.grants(self.session_token, publication_id):
                item = QListWidgetItem(
                    f"Група {grant.group_id} · "
                    + ("Доступ надано" if grant.active else "Відкликано")
                    + f" · r{grant.revision}"
                )
                item.setData(Qt.ItemDataRole.UserRole, grant)
                self.grant_groups.addItem(item)
            self.audit_text.setPlainText(
                "\n".join(
                    f"{entry.occurred_at:%d.%m.%Y %H:%M:%S} · автор {entry.actor_id} · "
                    f"група {entry.group_id} · {entry.operation} · "
                    f"r{entry.grant_revision}"
                    for entry in self.publications.audit(
                        self.session_token, publication_id
                    )
                )
            )
        except ApplicationError as error:
            self.add_grant.setEnabled(False)
            self.revoke_grant.setEnabled(False)
            self.message.setText(str(error))

    def confirm_grant(self, publication, group_id, active):
        box = QMessageBox(self)
        box.setWindowTitle("Підтвердити зміну доступу")
        operation = "Надати доступ" if active else "Відкликати доступ"
        snapshot = publication.manifest.snapshot
        box.setText(
            f"{operation}: сценарій {snapshot.scenario_id}, "
            f"версія {snapshot.scenario_version}, публікація {publication.id}, "
            f"навчальна група {group_id}.\nЗміну буде записано до аудиту."
        )
        action = box.addButton(operation, QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton("Скасувати", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() == action

    def change_grant(self, active):
        try:
            self._authorized()
            publication = self._selected_publication()
            publication_id = publication.id
            if active:
                group_id = self.available_group.currentData()
                grants = self.publications.grants(self.session_token, publication_id)
                revision = next(
                    (g.revision for g in grants if g.group_id == group_id), 0
                )
            else:
                item = self.grant_groups.currentItem()
                if item is None:
                    raise ApplicationError("Оберіть grant для відкликання.")
                grant = item.data(Qt.ItemDataRole.UserRole)
                group_id, revision = grant.group_id, grant.revision
            if not self.confirm_grant(publication, group_id, active):
                return
            self._authorized()
            if self._selected_publication().id != publication_id:
                raise ApplicationError(
                    "Публікацію змінено під час підтвердження. "
                    "Зміни доступу не виконано."
                )
            self.publications.change_grant(
                self.session_token,
                publication_id,
                group_id,
                active=active,
                expected_revision=revision,
            )
            self.changed = True
            self.refresh_grants()
            self.message.setText("Доступ змінено; подію додано до аудиту.")
        except ApplicationError as error:
            self.message.setText(str(error))

    def load_history(self, *args):
        if self.forced or self.history.currentData() is None:
            return
        try:
            self._authorized()
            previous = next(
                (
                    p.id
                    for p in self.publications.history(
                        self.session_token, self.expected.id
                    )
                    if p.manifest.snapshot.scenario_version == self.expected.version
                ),
                None,
            )
            if not self.discard_or_save():
                with QSignalBlocker(self.history):
                    self.history.setCurrentIndex(self.history.findData(previous))
                return
            self._authorized()
            publication = next(
                p
                for p in self.publications.history(self.session_token, self.expected.id)
                if p.id == self.history.currentData()
            )
            self.expected = self.integration.scenarios.get(
                self.session_token,
                self.expected.id,
                version=publication.manifest.snapshot.scenario_version,
            )
            self.load()
            self.tabs.setCurrentIndex(2)
        except (ApplicationError, StopIteration) as error:
            self.message.setText(str(error))

    def tab_changed(self, index):
        if self.tabs.widget(index) == self.web_tab and self.state.web:
            if self.browser is None:
                from cyberforge.ui.web_browser import WebBrowser

                self.browser = WebBrowser(self.web_tab)
                self.web_placeholder.hide()
                self.web_layout.addWidget(self.browser)
                self.browser.set_draft(self.state.web)

    def ask_unsaved(self):
        box = QMessageBox(self)
        box.setWindowTitle("Незбережені зміни")
        box.setText("Зберегти правки зв’язку та рубрики перед закриттям?")
        for standard, text in (
            (QMessageBox.StandardButton.Save, "Зберегти"),
            (QMessageBox.StandardButton.Discard, "Відкинути"),
            (QMessageBox.StandardButton.Cancel, "Залишитися"),
        ):
            box.addButton(standard).setText(text)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec()

    def discard_or_save(self):
        if not self.dirty:
            return True
        answer = self.ask_unsaved()
        if answer == QMessageBox.StandardButton.Discard:
            return True
        if answer != QMessageBox.StandardButton.Save:
            return False
        if self.link_values() != self._link_baseline and not self.save_link():
            return False
        if self.rubric_values() != self._rubric_baseline and not self.save_rubric():
            return False
        return True

    def _dispose_browser(self):
        if self.browser:
            self.browser.dispose()
            self.browser.deleteLater()
            self.browser = None

    def force_close(self):
        self.forced = True
        self.mail.set_draft(None)
        if self.browser:
            self.browser.set_draft(None)
        for field in (self.link_label, self.display_url, self.details, self.audit_text):
            field.clear()
        self.groups.clear()
        self.grant_groups.clear()
        self.state = self.report = None
        self.identity.clear()
        self.review_summary.clear()
        self.web_address.clear()
        self.history.clear()
        self.available_group.clear()
        self.reject()

    def reject(self):
        if self.forced or self.discard_or_save():
            self._dispose_browser()
            super().reject()

    def closeEvent(self, event):
        if self.forced or self.discard_or_save():
            self._dispose_browser()
            # Complete the dialog so asynchronous owners receive finished().
            super().reject()
            event.accept()
        else:
            event.ignore()
