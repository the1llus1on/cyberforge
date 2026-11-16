"""Guided instructor preparation using the existing publication services."""

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
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
from cyberforge.ui.preparation_widgets import (
    Disclosure,
    MaterialCards,
    PreparationStack,
    preparation_scroll,
)

APPLICABILITY = {
    "all_attempts": "Усі шляхи",
    "web_visited": "Лише після відвідування сайту",
    "web_not_visited": "Сайт не відвідано",
}
STATUS = {
    "PASS": "Готово",
    "WARNING": "Потребує перевірки",
    "BLOCKED": "Потрібно виправити",
}
CHECK_TITLES = {
    "active_draft": "Поточна чернетка",
    "email": "Електронний лист",
    "web": "Вебсторінка",
    "link": "Навчальне посилання",
    "rubric": "Критерії оцінювання",
    "security": "Безпека матеріалів",
    "semantic_review": "Змістова перевірка викладачем",
    "display_url_mismatch": "Відмінність адрес листа та сайту",
    "groups": "Навчальні групи",
    "instructor_confirmation": "Підтвердження викладача",
}


class IntegrationDialog(QDialog):
    constructor_requested = Signal(str)

    def __init__(
        self,
        integration: ScenarioIntegrationService,
        token,
        expected,
        *,
        owned,
        parent=None,
        history_only=False,
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
        self._step = 0
        self._view = "step"
        self._preview_origin = "step"
        self.setWindowTitle("Підготовка сценарію")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.resize(960, 680)
        self.setMinimumSize(520, 440)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)
        outer.addWidget(label("Підготовка сценарію", "heading"))
        self.identity = label("")
        outer.addWidget(self.identity)
        self.navigation = QWidget()
        nav = QHBoxLayout(self.navigation)
        nav.setContentsMargins(0, 0, 0, 0)
        self.step_group = QButtonGroup(self)
        self.step_buttons = []
        for index, title in enumerate(("Матеріали", "Оцінювання", "Публікація")):
            button = QPushButton(f"{index + 1}. {title}")
            button.setCheckable(True)
            button.setAccessibleName(f"Крок {index + 1}: {title}")
            self.step_group.addButton(button, index)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            nav.addWidget(button, 1)
            self.step_buttons.append(button)
        outer.addWidget(self.navigation)
        self.status_summary = label("")
        self.status_summary.setAccessibleName("Стан підготовки матеріалів")
        outer.addWidget(self.status_summary)
        self.content = PreparationStack()
        outer.addWidget(self.content, 1)
        self._build_materials()
        self._build_rubric()
        self._build_publication()
        self.steps = (self.materials_step, self.rubric_step, self.publication_step)
        self.mail = MailPreview()
        self.content.addWidget(self.mail)
        self.web_tab = QWidget()
        self.web_layout = QVBoxLayout(self.web_tab)
        self.web_layout.setContentsMargins(0, 0, 0, 0)
        self.web_placeholder = label("Відкрийте збережений сайт для перегляду.")
        self.web_layout.addWidget(self.web_placeholder)
        self.content.addWidget(self.web_tab)
        self._build_history()
        self._build_result()
        self.message = label("")
        outer.addWidget(self.message)
        footer = QHBoxLayout()
        self.back_button = QPushButton("Назад")
        self.back_button.clicked.connect(self.go_back)
        footer.addWidget(self.back_button)
        footer.addStretch()
        self.save_link_button = QPushButton("Зберегти зв’язок")
        self.save_link_button.clicked.connect(self.save_link)
        self.save_rubric_button = QPushButton("Зберегти критерії")
        self.save_rubric_button.clicked.connect(self.save_rubric)
        self.publish_button = QPushButton("Опублікувати сценарій")
        self.publish_button.setObjectName("primary")
        self.publish_button.clicked.connect(self.publish)
        self.next_button = QPushButton("Далі")
        self.next_button.clicked.connect(lambda: self.navigate(self._step + 1))
        for button in (
            self.save_link_button,
            self.save_rubric_button,
            self.publish_button,
            self.next_button,
        ):
            footer.addWidget(button)
        self.close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.close_buttons.button(QDialogButtonBox.StandardButton.Close).setText(
            "Закрити"
        )
        self.close_buttons.rejected.connect(self.reject)
        footer.addWidget(self.close_buttons)
        outer.addLayout(footer)
        self.groups.itemChanged.connect(self.invalidate_review)
        self.history.currentIndexChanged.connect(self.load_history)
        self.ack.toggled.connect(self._update_publish_enabled)
        self.link_label.textChanged.connect(self._editor_changed)
        self.display_url.textChanged.connect(self._editor_changed)
        for enabled, weight, app in self.criteria.values():
            enabled.toggled.connect(self._editor_changed)
            weight.textChanged.connect(self._editor_changed)
            app.currentIndexChanged.connect(self._editor_changed)
        self.load()
        self._loading = False
        self._show_step(0)
        if history_only:
            self.show_history()
        # Invalidate attestation after external changes; preserve editor buffers.
        self.source_timer = QTimer(self)
        self.source_timer.setInterval(2000)
        self.source_timer.timeout.connect(self._check_external_changes)
        self.source_timer.start()

    def _build_materials(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(label("Навчальні матеріали", "heading"))
        cards = []
        self.material_labels, self.preview_buttons, self.constructor_buttons = (
            {},
            {},
            {},
        )
        for kind, title, preview, edit in (
            (
                "email",
                "Електронний лист",
                "Переглянути лист",
                "Відкрити конструктор листа",
            ),
            ("web", "Вебсторінка", "Переглянути сайт", "Відкрити конструктор сайту"),
        ):
            card = QFrame()
            card.setObjectName("card")
            body = QVBoxLayout(card)
            body.setContentsMargins(14, 10, 14, 10)
            body.setSpacing(4)
            body.addWidget(label(title, "eyebrow"))
            summary = label("")
            body.addWidget(summary)
            self.material_labels[kind] = summary
            button = QPushButton(preview)
            button.setStyleSheet("padding: 5px 10px")
            button.clicked.connect(lambda checked=False, k=kind: self.open_preview(k))
            body.addWidget(button)
            self.preview_buttons[kind] = button
            constructor = QPushButton(edit)
            constructor.setStyleSheet("padding: 5px 10px")
            constructor.clicked.connect(
                lambda checked=False, k=kind: self.request_constructor(k)
            )
            body.addWidget(constructor)
            self.constructor_buttons[kind] = constructor
            cards.append(card)
        self.material_cards = MaterialCards(tuple(cards))
        layout.addWidget(self.material_cards)
        layout.addWidget(label("Навчальне посилання", "heading"))
        layout.addWidget(
            label(
                "Адреса показується лише в навчальному листі. Перехід веде до "
                "збереженого сайту цієї версії."
            )
        )
        self.link_label = QLineEdit()
        self.link_label.setMaxLength(200)
        self.link_label.setAccessibleName("Назва посилання")
        self.display_url = QLineEdit()
        self.display_url.setMaxLength(512)
        self.display_url.setAccessibleName("Відображувана адреса")
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.addRow("Назва посилання", self.link_label)
        form.addRow("Відображувана адреса", self.display_url)
        layout.addLayout(form)
        self.web_address = label("")
        layout.addWidget(self.web_address)
        self.url_warning = label("")
        layout.addWidget(self.url_warning)
        # Kept as a single validated service target, never an editable primary field.
        self.target = QComboBox()
        self.target.setEnabled(False)
        self.target.setMinimumContentsLength(8)
        self.target.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.target.setAccessibleName("Внутрішній ресурс, лише читання")
        technical = QWidget()
        technical_layout = QVBoxLayout(technical)
        technical_layout.setContentsMargins(0, 0, 0, 0)
        technical_layout.addWidget(self.target)
        self.source_details = label("")
        self.source_details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        technical_layout.addWidget(self.source_details)
        self.material_details = Disclosure("Технічні деталі", technical)
        layout.addWidget(self.material_details)
        layout.addStretch()
        self.materials_step = preparation_scroll(layout)
        self.material_cards.follow_viewport(self.materials_step.viewport())
        self.content.addWidget(self.materials_step)

    def _build_rubric(self):
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.addWidget(label("Критерії оцінювання", "heading"))
        self.preset_button = QPushButton("Використати базовий набір критеріїв")
        self.preset_button.setToolTip(
            "Редагований навчальний початок; не є науково валідованою "
            "методикою. Збереження виконується окремо."
        )
        self.preset_button.clicked.connect(self.apply_preset)
        layout.addWidget(self.preset_button)
        self.criteria, self.criterion_details, self.criterion_summaries = {}, {}, {}
        self.criterion_groups = {}
        for phase, title in (
            ("email", "Електронний лист"),
            ("transition", "Рішення про перехід"),
            ("web", "Вебсторінка"),
        ):
            layout.addWidget(label(title, "eyebrow"))
            self.criterion_groups[phase] = []
            for spec in (c for c in CRITERIA if c.phase == phase):
                enabled = QCheckBox(spec.label)
                enabled.setToolTip(spec.description)
                enabled.setAccessibleName(spec.label)
                weight = QLineEdit("1.0")
                weight.setMaxLength(32)
                validator = QDoubleValidator(0.0, 10000.0, 323, weight)
                from PySide6.QtCore import QLocale

                locale = QLocale.c()
                locale.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)
                validator.setLocale(locale)
                validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
                weight.setValidator(validator)
                weight.setAccessibleName("Додатна вага: " + spec.label)
                weight.setToolTip(
                    "Додатне скінченне число до 10000. Крапка або експоненційний "
                    "запис; точність зберігається."
                )
                app = QComboBox()
                app.setMinimumContentsLength(8)
                app.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )
                app.setAccessibleName("Застосовність: " + spec.label)
                for value in spec.applicability:
                    app.addItem(APPLICABILITY[value], value)
                detail = QWidget()
                form = QFormLayout(detail)
                form.setContentsMargins(18, 2, 6, 4)
                form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                form.addRow(label(spec.description))
                form.addRow("Вага", weight)
                form.addRow("Застосовність", app)
                form.addRow(Disclosure("Технічні дії", label(", ".join(spec.actions))))
                disclosure = Disclosure("Налаштувати: " + spec.label, detail)
                # Compact row holds selection, the exact current weight and disclosure.
                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(4)
                row.addWidget(enabled, 1)
                summary = label("")
                summary.setMinimumWidth(40)
                row.addWidget(summary)
                disclosure.toggle.setText("▸")
                disclosure.toggle.setMaximumWidth(40)
                disclosure.toggle.setStyleSheet("padding: 2px 6px")
                disclosure.toggle.toggled.connect(
                    lambda checked, b=disclosure.toggle: b.setText(
                        "▾" if checked else "▸"
                    )
                )
                row.addWidget(disclosure.toggle)
                layout.addWidget(row_widget)
                layout.addWidget(disclosure)
                self.criteria[spec.id] = enabled, weight, app
                self.criterion_details[spec.id] = disclosure
                self.criterion_summaries[spec.id] = summary
                self.criterion_groups[phase].append(spec.id)
        self.rubric_summary = label("")
        layout.addWidget(self.rubric_summary)
        layout.addStretch()
        self.rubric_step = preparation_scroll(layout)
        self.content.addWidget(self.rubric_step)

    def _build_publication(self):
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.addWidget(label("Перевірка та публікація", "heading"))
        self.review_summary = label("")
        layout.addWidget(self.review_summary)
        self.checklist_widget = QWidget()
        self.checklist = QVBoxLayout(self.checklist_widget)
        self.checklist.setContentsMargins(0, 0, 0, 0)
        self.checklist.setSpacing(2)
        layout.addWidget(self.checklist_widget)
        self.check_button = QPushButton("Оновити перевірку готовності")
        self.check_button.setStyleSheet("padding: 3px 8px")
        self.check_button.clicked.connect(self.check_readiness)
        layout.addWidget(self.check_button)
        layout.addWidget(label("Кому буде доступний сценарій?", "eyebrow"))
        self.groups = QListWidget()
        self.groups.setObjectName("membershipPicker")
        self.groups.setAccessibleName("Дозволені навчальні групи")
        self.groups.setFixedHeight(48)
        layout.addWidget(self.groups)
        self.group_hint = label("")
        layout.addWidget(self.group_hint)
        self.attestation_summary = label("")
        layout.addWidget(self.attestation_summary)
        self.ack = QCheckBox(
            "Я перевірив навчальні матеріали, їхній зв’язок і критерії оцінювання."
        )
        self.ack.setToolTip(
            "Підтвердження точних збережених джерел, вибраних груп і всіх "
            "зазначених попереджень."
        )
        # A wrapped native checkbox label keeps the control usable on narrow windows.
        self.ack.setText(
            "Я перевірив навчальні матеріали, їхній зв’язок\nі критерії оцінювання."
        )
        self.ack.setAccessibleName(
            "Я перевірив навчальні матеріали, їхній зв’язок і критерії оцінювання."
        )
        layout.addWidget(self.ack)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(140)
        self.technical_results = Disclosure(
            "Показати технічні результати", self.details
        )
        self.technical_results.toggle.setStyleSheet("padding: 3px 8px")
        layout.addWidget(self.technical_results)
        layout.addStretch()
        self.publication_step = preparation_scroll(layout)
        self.content.addWidget(self.publication_step)

    def _build_history(self):
        layout = QVBoxLayout()
        layout.addWidget(label("Опубліковані версії", "heading"))
        layout.addWidget(
            label(
                "Матеріали незмінні. Доступ груп змінюється окремо з "
                "підтвердженням та історією."
            )
        )
        self.history = QComboBox()
        self.history.setAccessibleName("Опублікована версія сценарію")
        layout.addWidget(self.history)
        previews = QHBoxLayout()
        self.open_history = QPushButton("Переглянути матеріали")
        self.open_history.clicked.connect(lambda: self.open_preview("email"))
        previews.addWidget(self.open_history)
        self.history_web = QPushButton("Переглянути сайт")
        self.history_web.clicked.connect(lambda: self.open_preview("web"))
        previews.addWidget(self.history_web)
        layout.addLayout(previews)
        layout.addWidget(label("Керувати доступом", "eyebrow"))
        self.grant_groups = QListWidget()
        self.grant_groups.setMinimumHeight(80)
        self.grant_groups.setMaximumHeight(140)
        layout.addWidget(self.grant_groups)
        self.available_group = QComboBox()
        self.available_group.setMinimumContentsLength(10)
        self.available_group.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.available_group.setAccessibleName("Група для надання доступу")
        layout.addWidget(self.available_group)
        self.add_grant = QPushButton("Надати доступ групі")
        self.revoke_grant = QPushButton("Відкликати вибраний доступ")
        self.add_grant.clicked.connect(lambda: self.change_grant(True))
        self.revoke_grant.clicked.connect(lambda: self.change_grant(False))
        layout.addWidget(self.add_grant)
        layout.addWidget(self.revoke_grant)
        self.audit_text = QPlainTextEdit()
        self.audit_text.setReadOnly(True)
        self.audit_text.setMinimumHeight(130)
        self.audit_details = Disclosure("Історія змін доступу", self.audit_text)
        layout.addWidget(self.audit_details)
        self.published_definition = QPlainTextEdit()
        self.published_definition.setReadOnly(True)
        self.published_definition.setMinimumHeight(130)
        layout.addWidget(
            Disclosure(
                "Зв’язок і критерії опублікованої версії", self.published_definition
            )
        )
        layout.addStretch()
        self.history_view = preparation_scroll(layout)
        self.content.addWidget(self.history_view)

    def _build_result(self):
        self.result_view = QWidget()
        layout = QVBoxLayout(self.result_view)
        layout.addStretch()
        layout.addWidget(label("Сценарій опубліковано", "heading"))
        self.result_summary = label("")
        layout.addWidget(self.result_summary)
        layout.addWidget(
            label(
                "Проходження слухачами буде доступне після реалізації "
                "відповідного навчального модуля."
            )
        )
        self.view_publication = QPushButton("Переглянути публікацію")
        self.view_publication.clicked.connect(self.show_history)
        layout.addWidget(self.view_publication)
        self.return_scenario = QPushButton("Повернутися до сценарію")
        self.return_scenario.clicked.connect(self.reject)
        layout.addWidget(self.return_scenario)
        layout.addStretch()
        self.content.addWidget(self.result_view)

    def _show_step(self, index):
        self._step, self._view = index, "step"
        self.content.setCurrentWidget(self.steps[index])
        self._update_navigation()

    def navigate(self, index):
        if not 0 <= index < 3:
            return False
        if self._view == "step" and self._step == index:
            self._update_navigation()
            return True
        if not self.discard_or_save():
            self._update_navigation()
            return False
        self._show_step(index)
        if index == 2:
            self._check_external_changes()
        self.step_buttons[index].setFocus()
        return True

    def _update_navigation(self):
        preparing = self._view == "step"
        self.navigation.setVisible(
            self._view not in ("history", "result")
            and self._preview_origin != "history"
        )
        self.status_summary.setVisible(self._view not in ("history", "result"))
        for i, button in enumerate(self.step_buttons):
            button.setChecked(i == self._step)
            button.setAccessibleDescription(
                ("Поточний крок. " if i == self._step else "") + button.toolTip()
            )
        self.back_button.setVisible(
            self._view in ("email", "web") or (preparing and self._step > 0)
        )
        self.back_button.setText(
            "Повернутися до публікацій"
            if self._preview_origin == "history"
            else "Повернутися до матеріалів"
            if self._view in ("email", "web")
            else "Назад"
        )
        self.next_button.setVisible(preparing and self._step < 2)
        self.save_link_button.setVisible(preparing and self._step == 0)
        self.save_rubric_button.setVisible(preparing and self._step == 1)
        self.publish_button.setVisible(preparing and self._step == 2)

    def open_preview(self, kind):
        if kind not in ("email", "web") or not self.discard_or_save():
            return False
        try:
            self._authorized()
            # Read persisted sources; never substitute content for a stale Web.
            state = self.integration.inspect(self.session_token, self.expected)
            if state.checked_sources != self.state.checked_sources:
                self.invalidate_review()
                raise ApplicationError(
                    "Матеріали змінилися. Закрийте огляд і відкрийте сценарій повторно."
                )
            if getattr(state, kind) is None:
                raise ApplicationError(
                    "Збережений матеріал відсутній або потребує оновлення."
                )
            if self._view not in ("email", "web"):
                self._preview_origin = "history" if self._view == "history" else "step"
            self._view = kind
            if kind == "web" and self.browser is None:
                from cyberforge.ui.web_browser import WebBrowser

                self.browser = WebBrowser(self.web_tab)
                self.web_placeholder.hide()
                self.web_layout.addWidget(self.browser)
                self.browser.set_draft(state.web)
            self.content.setCurrentWidget(
                self.mail if kind == "email" else self.web_tab
            )
            self._update_navigation()
            self.back_button.setFocus()
            return True
        except ApplicationError as error:
            self.message.setText(str(error))
            return False

    def go_back(self):
        if self._view in ("email", "web"):
            if not self.discard_or_save():
                return
            if self._preview_origin == "history":
                self._view = "history"
                self.content.setCurrentWidget(self.history_view)
                self._update_navigation()
            else:
                self._show_step(0)
        else:
            self.navigate(self._step - 1)

    def show_history(self):
        if not self.discard_or_save():
            return False
        if not self.history.count():
            self.message.setText("Опублікованих версій поки немає.")
            return False
        if self.history.currentData() is None:
            self.history.setCurrentIndex(0)
        else:
            self.load_history()
        return True

    def request_constructor(self, kind):
        if not self.writable or not self.discard_or_save():
            return
        try:
            self._authorized()
        except ApplicationError as error:
            self.message.setText(str(error))
            return
        self.constructor_requested.emit(kind)
        self.reject()

    def _restore_editors(self):
        self._loading = True
        name, url, _ = self._link_baseline
        self.link_label.setText(name)
        self.display_url.setText(url)
        for key, enabled, weight, app in self._rubric_baseline:
            checkbox, editor, selector = self.criteria[key]
            checkbox.setChecked(enabled)
            editor.setText(weight)
            selector.setCurrentIndex(selector.findData(app))
        self._loading = False
        self._editor_changed()

    def _editor_changed(self, *args):
        if self._loading:
            return
        self.ack.setChecked(False)
        self._refresh_rubric()
        self._update_url_warning()
        self._update_publish_enabled()

    def _update_url_warning(self):
        mismatch = bool(
            self.state.web
            and self.display_url.text()
            and self.display_url.text() != self.state.web.page.display_url
        )
        self.url_warning.setText(
            "Адреса в листі відрізняється від адреси сайту. Перевірте, чи це "
            "передбачено навчальним сценарієм."
            if mismatch
            else ""
        )
        self.url_warning.setVisible(mismatch)

    def _refresh_materials(self):
        statuses = {}
        for name in ("email", "web", "link", "rubric"):
            check = next(c for c in self.state.checks if c.check_id == name)
            statuses[name] = (
                "збережено"
                if check.status == "PASS"
                else "потребує оновлення"
                if self.state.checked_sources[name + "_revision"]
                else "не збережено"
            )
        self.status_summary.setText(
            "Лист: "
            + statuses["email"]
            + " · Сайт: "
            + statuses["web"]
            + " · Зв’язок: "
            + statuses["link"]
            + " · Критерії: "
            + statuses["rubric"]
        )
        for name in ("email", "web"):
            material = getattr(self.state, name)
            title = (
                (
                    material.artifact.subject
                    if name == "email"
                    else material.page.tab_title
                )
                if material
                else "Матеріал відсутній або застарілий"
            )
            self.material_labels[name].setText(
                title + "\n" + statuses[name].capitalize()
            )
            self.preview_buttons[name].setEnabled(material is not None)
            self.constructor_buttons[name].setVisible(self.writable)
        self.source_details.setText(
            f"Сценарій {self.expected.id} · Версія {self.expected.version}\n"
            + "\n".join(
                f"{key}: {value}" for key, value in self.state.checked_sources.items()
            )
            + (
                "\nПоходження зв’язку: " + self.state.link.linkage_provenance
                if self.state.link
                else ""
            )
        )
        self.source_details.setToolTip(self.source_details.text())
        self._update_url_warning()
        step_checks = (
            ("email", "web", "link"),
            ("rubric",),
            ("security", "semantic_review"),
        )
        for button, ids in zip(self.step_buttons, step_checks, strict=True):
            relevant = [c for c in self.state.checks if c.check_id in ids]
            status = (
                "BLOCKED"
                if any(c.status == "BLOCKED" for c in relevant)
                else "WARNING"
                if any(c.status == "WARNING" for c in relevant)
                else "PASS"
            )
            title = ("Матеріали", "Оцінювання", "Публікація")[
                self.step_buttons.index(button)
            ]
            marker = "✓" if status == "PASS" else "!"
            button.setText(f"{self.step_buttons.index(button) + 1}. {title} {marker}")
            button.setToolTip(STATUS[status])
            button.setProperty("preparationStatus", status)
            button.style().unpolish(button)
            button.style().polish(button)
        self._update_navigation()

    def _refresh_rubric(self):
        selected = []
        errors = []
        for key, (enabled, weight, app) in self.criteria.items():
            self.criterion_summaries[key].setText(weight.text())
            self.criterion_summaries[key].setToolTip(APPLICABILITY[app.currentData()])
            if enabled.isChecked():
                try:
                    selected.append(
                        criterion(key, float(weight.text()), app.currentData())
                    )
                except (ValueError, TypeError):
                    errors.append(
                        enabled.text()
                        + ": вага має бути додатним скінченним числом до 10000."
                    )
        count = sum(c[0].isChecked() for c in self.criteria.values())
        text = f"Обрано {count} із {len(CRITERIA)} критеріїв"
        if not selected:
            errors.append("Оберіть хоча б один критерій.")
        elif not any(
            c.phase != "web" and c.applicability != "web_visited" for c in selected
        ):
            errors.append("Додайте критерій для безпечного шляху без відкриття сайту.")
        self.rubric_summary.setText(
            text
            + "\n"
            + (
                "\n".join(errors)
                if errors
                else "Підтримується безпечний шлях без відкриття сайту."
            )
        )

    def confirm_preset(self):
        box = QMessageBox(self)
        box.setWindowTitle("Замінити набір критеріїв?")
        box.setText(
            "Базовий набір замінить поточні правки редактора. Збережена "
            "рубрика зміниться лише після окремого збереження."
        )
        replace = box.addButton("Замінити", QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton("Залишитися", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() == replace

    def apply_preset(self):
        if not self.writable:
            return
        if (
            self.state.rubric or self.rubric_values() != self._rubric_baseline
        ) and not self.confirm_preset():
            return
        self._loading = True
        for enabled, weight, app in self.criteria.values():
            enabled.setChecked(True)
            weight.setText("1.0")
            app.setCurrentIndex(0)
        self._loading = False
        self._editor_changed()
        self.message.setText(
            "Базовий набір підготовлено. Перевірте й збережіть критерії окремо."
        )

    def _selected_group_names(self):
        return [
            self.groups.item(i).text()
            for i in range(self.groups.count())
            if self.groups.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _update_publish_enabled(self, *args):
        self.publish_button.setEnabled(
            bool(
                self.writable
                and self.report
                and self._publication_inputs_ready(self.report)
                and self.ack.isChecked()
                and not self.dirty
            )
        )

    def _render_readiness(self):
        while self.checklist.count():
            item = self.checklist.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.check_rows = {}
        if self.report is None:
            self.review_summary.setText(
                "Огляд потребує оновлення. Повторно відкрийте сценарій "
                "після зміни матеріалів."
            )
            self.attestation_summary.clear()
            return
        self.review_summary.setText(
            "Матеріали готові до підтвердження."
            if self.report.technical_ready
            else "Перш ніж публікувати, виправте зазначені пункти."
        )
        corrections = {
            "email": ("Створити лист", lambda: self.request_constructor("email")),
            "web": ("Оновити сайт", lambda: self.request_constructor("web")),
            "link": ("Налаштувати посилання", lambda: self.navigate(0)),
            "rubric": ("Налаштувати критерії", lambda: self.navigate(1)),
            "display_url_mismatch": ("Перевірити адреси", lambda: self.navigate(0)),
            "semantic_review": ("Переглянути матеріали", lambda: self.navigate(0)),
            "security": ("Перевірити матеріали", lambda: self.navigate(0)),
            "groups": ("Вибрати групи", self.groups.setFocus),
            "instructor_confirmation": ("Переглянути підтвердження", self.ack.setFocus),
        }
        for check in self.report.checks:
            # Group selection and attestation have dedicated controls below.
            # The complete service report remains available in technical results.
            if check.check_id in ("groups", "instructor_confirmation") or (
                check.check_id == "active_draft" and check.status == "PASS"
            ):
                continue
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            text = label(
                CHECK_TITLES.get(check.check_id, "Перевірка матеріалів")
                + " · "
                + STATUS[check.status]
            )
            text.setToolTip(check.explanation + "\n" + check.correction)
            row.addWidget(text, 1)
            if check.status != "PASS" and check.check_id in corrections:
                title, action = corrections[check.check_id]
                button = QPushButton(title)
                button.setStyleSheet("padding: 3px 8px")
                button.clicked.connect(action)
                button.setEnabled(self.writable)
                row.addWidget(button)
            self.checklist.addWidget(row_widget)
            self.check_rows[check.check_id] = row_widget
        self.group_hint.setText(
            "" if self.selected_groups() else "Виберіть хоча б одну навчальну групу."
        )
        self.group_hint.setVisible(not self.selected_groups())
        warnings = [
            CHECK_TITLES.get(code, code)
            for code in self.report.acknowledgement_requirements
        ]
        self.attestation_summary.setText(
            f"Підтвердження: сценарій {self.expected.id}, "
            f"версія {self.expected.version}. "
            + "Критеріїв: "
            + str(len(self.state.rubric.criteria) if self.state.rubric else 0)
            + ".\n"
            + "Групи: "
            + (", ".join(self._selected_group_names()) or "не вибрано")
            + "\nПопередження для підтвердження: "
            + ("; ".join(warnings) or "немає")
        )

    def _check_external_changes(self):
        if self.forced or not self.isVisible() or self.state is None:
            return
        try:
            self._authorized()
            groups = GroupService(self.integration.accounts).list_groups(
                self.session_token
            )
            if {g.id: g.name for g in groups} != self._group_names:
                selected = self.selected_groups()
                self._loading = True
                self.groups.clear()
                self.available_group.clear()
                self._group_names = {g.id: g.name for g in groups}
                for group in groups:
                    item = QListWidgetItem(group.name)
                    item.setData(Qt.ItemDataRole.UserRole, group.id)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if group.id in selected
                        else Qt.CheckState.Unchecked
                    )
                    self.groups.addItem(item)
                    self.available_group.addItem(group.name, group.id)
                self._loading = False
                self.check_readiness()
                self.refresh_grants()
            current = self.readiness.evaluate(
                self.session_token,
                self.expected,
                selected_group_ids=self.selected_groups(),
            )
            if current.checked_sources != self.state.checked_sources or (
                self.report
                and current.review_fingerprint != self.report.review_fingerprint
            ):
                self.report = None
                self.ack.setChecked(False)
                self._update_publish_enabled()
                self.message.setText(
                    "Матеріали або групи змінилися. Правки редактора збережено в "
                    "пам’яті; повторно відкрийте сценарій."
                )
                self.status_summary.setText(
                    "Матеріали змінилися · потрібен повторний огляд"
                )
            elif any(
                c.check_id == "groups" and c.status == "BLOCKED" for c in current.checks
            ):
                self.ack.setChecked(False)
                self.report = current
                self._update_publish_enabled()
        except ApplicationError as error:
            self.report = None
            self.ack.setChecked(False)
            self._update_publish_enabled()
            self.message.setText(str(error))

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
        self._loading = True
        selected_groups = self.selected_groups()
        self.state = self.integration.inspect(self.session_token, self.expected)
        self.writable = (
            self.owned
            and not self.expected.archived
            and self.expected.status == "draft"
        )
        self.identity.setText(
            f"Сценарій {self.expected.id} · Версія {self.expected.version} · "
            f"{self.expected.status.label}"
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
            "Адреса сайту: "
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
        self.target.setEnabled(False)
        self.preset_button.setEnabled(self.writable)
        self.mail.set_draft(self.state.email)
        self.mail.set_link(self.state.link)
        if self.state.email:
            self.mail.open_message(0)
        if self.browser:
            self.browser.set_draft(self.state.web)
        self._loading = True
        self.groups.clear()
        self.available_group.clear()
        self._group_names = {}
        for group in GroupService(self.integration.accounts).list_groups(
            self.session_token
        ):
            self._group_names[group.id] = group.name
            item = QListWidgetItem(group.name)
            item.setData(Qt.ItemDataRole.UserRole, group.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if group.id in selected_groups
                else Qt.CheckState.Unchecked
            )
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
                    f"Версія {publication.manifest.snapshot.scenario_version} · "
                    "Опубліковано "
                    + publication.manifest.published_at.astimezone().strftime(
                        "%d.%m.%Y %H:%M"
                    ),
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
        self._refresh_materials()
        self._refresh_rubric()

    def _reload_state(self):
        self.state = self.integration.inspect(self.session_token, self.expected)
        self.mail.set_draft(self.state.email)
        self.mail.set_link(self.state.link)
        if self.state.email:
            self.mail.open_message(0)
        self.invalidate_review()
        self._refresh_materials()
        self._refresh_rubric()

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
            self._refresh_materials()
            self._render_readiness()
            self._update_publish_enabled()
            self.message.clear()
        except ApplicationError as error:
            self.message.setText(str(error))
            self.publish_button.setEnabled(False)
            self.report = None
            self.ack.setChecked(False)
            self._render_readiness()

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
        box = QMessageBox(self)
        box.setWindowTitle("Підтвердити публікацію")
        box.setText(
            f"Сценарій {self.expected.id}, версія {self.expected.version}\n"
            + "Групи: "
            + ", ".join(groups)
            + "\nОпублікований вміст стане незмінним. Підтвердити?"
        )
        publish = box.addButton("Опублікувати", QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton("Скасувати", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() == publish

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
            selected_names = self._selected_group_names()
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
            self.result_summary.setText(
                f"Версію {self.expected.version} зафіксовано. Навчальні матеріали та "
                "критерії оцінювання захищені від змін.\nГрупи: "
                + ", ".join(selected_names)
            )
            self._view = "result"
            self.content.setCurrentWidget(self.result_view)
            self._update_navigation()
            self.message.clear()
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
            group_names = dict(self._group_names)
            for grant in self.publications.grants(self.session_token, publication_id):
                item = QListWidgetItem(
                    group_names.get(grant.group_id, f"Група {grant.group_id}")
                    + " · "
                    + ("Доступ надано" if grant.active else "Відкликано")
                )
                item.setToolTip(f"Ревізія доступу: {grant.revision}")
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
                    raise ApplicationError("Оберіть групу для відкликання доступу.")
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
            self.published_definition.setPlainText(
                "Навчальне посилання\n"
                + self.state.link.link_label
                + "\n"
                + self.state.link.display_url
                + "\n\nКритерії оцінювання\n"
                + "\n".join(
                    f"{c.label} · вага {c.weight} · {APPLICABILITY[c.applicability]}"
                    for c in self.state.rubric.criteria
                )
            )
            self._view = "history"
            self.content.setCurrentWidget(self.history_view)
            self._update_navigation()
        except (ApplicationError, StopIteration) as error:
            self.message.setText(str(error))

    def ask_unsaved(self):
        box = QMessageBox(self)
        box.setWindowTitle("Незбережені зміни")
        box.setText("Зберегти правки зв’язку та критеріїв перед переходом?")
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
            self._restore_editors()
            return True
        if answer != QMessageBox.StandardButton.Save:
            return False
        if self.link_values() != self._link_baseline and not self.save_link():
            return False
        if self.rubric_values() != self._rubric_baseline and not self.save_rubric():
            return False
        return True

    def _dispose_browser(self):
        self.source_timer.stop()
        if self.browser:
            self.browser.dispose()
            self.browser.deleteLater()
            self.browser = None

    def force_close(self):
        self.forced = True
        self._loading = True
        self.source_timer.stop()
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
        self.status_summary.clear()
        self.source_details.clear()
        self.attestation_summary.clear()
        self.published_definition.clear()
        self.result_summary.clear()
        for summary in self.material_labels.values():
            summary.clear()
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
