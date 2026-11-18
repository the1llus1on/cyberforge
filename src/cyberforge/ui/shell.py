"""Main desktop shell. Mode navigation grants no access to scenario data."""

from PySide6.QtCore import QSignalBlocker, QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.accounts import AccountService
from cyberforge.application.analytics import ScenarioAnalyticsService
from cyberforge.application.data_recovery import DataRecoveryService
from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.evaluations import EvaluationService
from cyberforge.application.learner_attempts import LearnerAttemptService
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import (
    PublicationAccessService,
    ScenarioPublicationService,
)
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import (
    AccessDenied,
    ApplicationError,
    Role,
    Workspace,
)
from cyberforge.domain.scenarios import Scenario
from cyberforge.groups.service import GroupService
from cyberforge.llm.factory import create_gateway
from cyberforge.ui.account_pages import AccountPage
from cyberforge.ui.admin_page import AdminPage
from cyberforge.ui.analytics_page import AnalyticsPage
from cyberforge.ui.clipboard_shortcuts import ClipboardShortcuts
from cyberforge.ui.data_recovery import RecoveryPage
from cyberforge.ui.icons import icon
from cyberforge.ui.learner_pages import LearnerCatalogPage
from cyberforge.ui.learner_results import LearnerResultsPage
from cyberforge.ui.navigation import AuthenticationState, NavigationState, View
from cyberforge.ui.pages import WorkspacePage, label
from cyberforge.ui.scenario_page import ScenarioPage
from cyberforge.ui.window_geometry import window_geometry


def button(text: str, icon_name: str, tooltip: str) -> QPushButton:
    result = QPushButton(text)
    result.setIcon(icon(icon_name))
    result.setIconSize(QSize(22, 22))
    result.setToolTip(tooltip)
    result.setAccessibleName(tooltip)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result


class MainWindow(QMainWindow):
    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Native decorations are known after show; setGeometry used client bounds.
        # Keep the initial frame visible without policing subsequent user resizes.
        available = self.screen().availableGeometry()
        frame = self.frameGeometry()
        left = min(
            max(frame.left(), available.left()),
            max(available.left(), available.right() - frame.width() + 1),
        )
        top = min(
            max(frame.top(), available.top()),
            max(available.top(), available.bottom() - frame.height() + 1),
        )
        if frame.topLeft().toTuple() != (left, top):
            self.move(left, top)

    def __init__(
        self,
        accounts: AccountService,
        emails: EmailMaterialService | None = None,
        webs: WebMaterialService | None = None,
        recovery: DataRecoveryService | None = None,
    ) -> None:
        super().__init__()
        self.accounts = accounts
        self.groups = GroupService(accounts)
        self.scenarios = ScenarioService(accounts)
        self.emails = emails or EmailMaterialService(self.scenarios, create_gateway())
        publication_service = ScenarioPublicationService(
            ScenarioReadinessService(
                ScenarioIntegrationService(webs or WebMaterialService(self.emails))
            )
        )
        self.learner_attempts = LearnerAttemptService(
            PublicationAccessService(publication_service)
        )
        self.evaluations = EvaluationService(self.learner_attempts)
        self.mentor_feedback = MentorFeedbackService(
            self.evaluations, self.emails.gateway
        )
        self._closing_pending = False
        self._recovery = recovery
        self._restore_request: str | None = None
        self.selected_scenario_id: int | None = None
        self._catalog: tuple[Scenario, ...] = ()
        self._token: str | None = None
        self.setWindowTitle("CyberForge")
        bounds, minimum = window_geometry(self.screen().availableGeometry())
        self.setMinimumSize(minimum)
        self.setGeometry(bounds)
        self.clipboard_shortcuts = ClipboardShortcuts(self)
        self.clipboard_shortcuts.bind(QApplication.instance())
        self.authentication_state = AuthenticationState.GUEST
        self.navigation = NavigationState()
        root = QWidget()
        root.setMinimumSize(860, 620)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # RDP/compositors may force a frame below advertised minimum hints.
        # A root scroll area keeps navigation and content reachable in that case.
        self.root_scroll = QScrollArea()
        self.root_scroll.setWidgetResizable(True)
        self.root_scroll.setWidget(root)
        self.setCentralWidget(self.root_scroll)
        topbar = QFrame()
        self.topbar = topbar
        topbar.setObjectName("topbar")
        top = QHBoxLayout(topbar)
        top.setContentsMargins(16, 10, 24, 10)
        top.setSpacing(6)
        self.back_button = button("", "back", "Назад")
        self.forward_button = button("", "forward", "Вперед")
        self.back_button.clicked.connect(self._back)
        self.forward_button.clicked.connect(self._forward)
        top.addWidget(self.back_button)
        top.addWidget(self.forward_button)
        brand = label("CyberForge", "heading")
        brand.setObjectName("brand")
        top.addSpacing(16)
        top.addWidget(brand)
        top.addStretch()
        self.context_label = label("Головна")
        top.addWidget(self.context_label)
        top.addSpacing(16)
        badge = label("Гостьовий режим")
        self.badge = badge
        badge.setObjectName("badge")
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        top.addWidget(badge)
        outer.addWidget(topbar)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)
        rail = QFrame()
        self.rail = rail
        rail.setObjectName("rail")
        rail.setFixedWidth(76)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 18, 12, 18)
        rail_layout.setSpacing(12)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons: dict[View, QPushButton] = {}
        entries = (
            (View.HOME, "home", "Головна"),
            (View.CONSTRUCTOR, "plus", "Конструктор — перегляд оболонки"),
            (View.ANALYTICS, "chart", "Аналіз — перегляд оболонки"),
            (View.MY_SCENARIOS, "book", "Мої сценарії"),
            (View.MY_RESULTS, "chart", "Мої результати"),
            (View.ADMIN, "settings", "Адміністрування"),
            (View.SETTINGS, "settings", "Налаштування"),
            (View.PROFILE, "profile", "Профіль"),
        )
        for view, icon_name, tooltip in entries:
            if view == View.SETTINGS:
                rail_layout.addStretch()
            control = button("", icon_name, tooltip)
            control.setCheckable(True)
            control.setFixedSize(50, 48)
            control.clicked.connect(
                lambda checked=False, target=view: self.navigate(target)
            )
            self.nav_group.addButton(control)
            self.nav_buttons[view] = control
            rail_layout.addWidget(control)
        body.addWidget(rail)
        self.scenario_panel = QFrame()
        self.scenario_panel.setObjectName("catalog")
        self.scenario_panel.setFixedWidth(256)
        catalog = QVBoxLayout(self.scenario_panel)
        catalog.setContentsMargins(20, 26, 20, 22)
        catalog.setSpacing(18)
        catalog.addWidget(label("РОБОЧИЙ ПРОСТІР", "eyebrow"))
        catalog.addWidget(label("Сценарії", "heading"))
        self.new_scenario_button = QPushButton("+ Новий сценарій")
        self.new_scenario_button.setObjectName("newScenario")
        self.new_scenario_button.setEnabled(False)
        self.new_scenario_button.setToolTip("Відкрити форму нового сценарію")
        self.new_scenario_button.clicked.connect(self._new_scenario)
        catalog.addWidget(self.new_scenario_button)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Пошук сценаріїв")
        self.search.setAccessibleName("Пошук сценаріїв")
        self.search.setEnabled(False)
        self.search.setToolTip("Пошук за ID, темою або статусом")
        self.search.textChanged.connect(self._filter_catalog)
        catalog.addWidget(self.search)
        self.archive_filter = QCheckBox("Архівні сценарії")
        self.archive_filter.toggled.connect(self._archive_filter_changed)
        catalog.addWidget(self.archive_filter)
        catalog.addSpacing(18)
        self.catalog_title = label("Каталог недоступний", "heading")
        catalog.addWidget(self.catalog_title)
        self.catalog_hint = label(
            "Увійдіть до облікового запису, щоб побачити ваші сценарії."
        )
        catalog.addWidget(self.catalog_hint)
        self.scenario_list = QListWidget()
        self.scenario_list.setWordWrap(True)
        self.scenario_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scenario_list.currentItemChanged.connect(self._select_scenario)
        catalog.addWidget(self.scenario_list, 1)
        body.addWidget(self.scenario_panel)
        self.workspace = QStackedWidget()
        self.pages: dict[View, QWidget] = {}
        self.containers: dict[View, QScrollArea] = {}
        for view in View:
            if view == View.CONSTRUCTOR:
                page = ScenarioPage(
                    self.scenarios, lambda: self._token, self.emails, webs
                )
                self.scenario_page = page
                page.saved.connect(self._scenario_saved)
                page.archive_changed.connect(self._scenario_archive_changed)
            elif view == View.MY_SCENARIOS:
                page = LearnerCatalogPage(self.learner_attempts, lambda: self._token)
                self.learner_catalog = page
            elif view == View.MY_RESULTS:
                page = LearnerResultsPage(
                    self.evaluations, self.mentor_feedback, lambda: self._token
                )
                self.learner_history = page
            elif view == View.ANALYTICS:
                page = AnalyticsPage(ScenarioAnalyticsService(self.evaluations))
                self.analytics_page = page
                page.login_button.clicked.connect(lambda: self.navigate(View.PROFILE))
            elif view == View.PROFILE:
                page = AccountPage(self.accounts)
                self.account_page = page
                page.authenticated.connect(self._authenticated)
                page.signed_out.connect(self._signed_out)
                page.close_requested.connect(lambda: self.navigate(View.HOME))
            elif view == View.ADMIN:
                page = AdminPage(
                    self.accounts, self.groups, lambda: self._token, self._sync_session
                )
                if self._recovery is not None:
                    page.tabs.addTab(
                        RecoveryPage(
                            self._recovery, lambda: self._token, self._request_restore
                        ),
                        "Резервні копії",
                    )
                self.admin_page = page
            else:
                page = WorkspacePage(view)
                page.profile_requested.connect(lambda: self.navigate(View.PROFILE))
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            if isinstance(page, AnalyticsPage):
                page.reveal_details.connect(scroll.ensureWidgetVisible)
            scroll.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self.pages[view] = page
            self.containers[view] = scroll
            self.workspace.addWidget(scroll)
        body.addWidget(self.workspace, 1)
        self.session_timer = QTimer(self)
        self.session_timer.setInterval(1000)
        self.session_timer.timeout.connect(self._sync_session)
        self.session_timer.start()
        self._render()

    def _authenticated(self, token: str) -> None:
        self.analytics_page.invalidate()
        self.learner_catalog.invalidate()
        self.learner_history.invalidate()
        self.scenario_page.email_page.invalidate()
        self.scenario_page.web_page.invalidate()
        self._token = token
        self.authentication_state = AuthenticationState.AUTHENTICATED
        self.navigation.reset()
        if self._refresh_profile():
            self._render()

    def _refresh_profile(self) -> bool:
        try:
            self.account_page.refresh(self._token)
        except ApplicationError as error:
            self._signed_out()
            self.statusBar().showMessage(str(error), 5000)
            return False
        return True

    def _signed_out(self) -> None:
        self.analytics_page.invalidate()
        self.learner_catalog.invalidate()
        self.learner_history.invalidate()
        self.accounts.logout(self._token)
        self._token = None
        self.authentication_state = AuthenticationState.GUEST
        self.navigation.reset()
        self.account_page.refresh(None)
        self.admin_page.clear()
        self.scenario_page.clear()
        self.selected_scenario_id = None
        self._show_scenario()
        self._catalog = ()
        with QSignalBlocker(self.scenario_list):
            self.scenario_list.clear()
        self.search.clear()
        with QSignalBlocker(self.archive_filter):
            self.archive_filter.setChecked(False)
        self._render()

    def _sync_session(self) -> None:
        if self._token:
            try:
                self.accounts.current(self._token)
            except ApplicationError as error:
                self._signed_out()
                self.statusBar().showMessage(str(error), 5000)
            else:
                self._render()
                if self.navigation.current == View.ANALYTICS:
                    self.analytics_page.check_access()

    def _allowed(self, view: View) -> bool:
        if self._token is None:
            return view in (View.HOME, View.PROFILE, View.SETTINGS)
        try:
            self.accounts.current(self._token)
        except ApplicationError as error:
            self._signed_out()
            self.statusBar().showMessage(str(error), 5000)
            return False
        if view.value in {workspace.value for workspace in Workspace}:
            try:
                self.accounts.authorize_workspace(self._token, Workspace(view.value))
            except AccessDenied:
                return False
            except ApplicationError as error:
                self._signed_out()
                self.statusBar().showMessage(str(error), 5000)
                return False
        return True

    def _request_restore(self, identifier: str) -> None:
        self._restore_request = identifier
        self.close()

    def closeEvent(self, event) -> None:
        if self._closing_pending:
            if self._generation_running():
                event.ignore()
                QTimer.singleShot(50, self.close)
                return
            self._dispose_browser()
            super().closeEvent(event)
            return
        if not self.scenario_page.can_leave():
            self._restore_request = None
            event.ignore()
            return
        identifier, self._restore_request = self._restore_request, None
        if identifier is not None and self._recovery is not None:
            try:
                self._recovery.plan_restore(self._token, identifier)
            except ApplicationError as error:
                self.statusBar().showMessage(str(error), 5000)
                event.ignore()
                return
        self.session_timer.stop()
        self._signed_out()
        if self._generation_running():
            self._closing_pending = True
            event.ignore()
            self.centralWidget().setEnabled(False)
            self.statusBar().showMessage("Завершення поточного запиту перед закриттям…")
            QTimer.singleShot(50, self.close)
            return
        self._dispose_browser()
        super().closeEvent(event)

    def _dispose_browser(self) -> None:
        browser = self.scenario_page.web_page.browser
        if browser is not None:
            browser.dispose()

    def _generation_running(self) -> bool:
        return (
            self.scenario_page.email_page.running
            or self.scenario_page.web_page.running
            or self.learner_history.running
            or self.analytics_page.running
        )

    def navigate(self, view: View) -> None:
        if not self._allowed(view):
            self.statusBar().showMessage("Доступ заборонено.", 5000)
            self._render()
            return
        if view == self.navigation.current:
            self._render()
            return
        if not self.scenario_page.can_leave():
            self._render()
            return
        if view != View.PROFILE:
            self.account_page.clear()
        if view == View.PROFILE and not self._refresh_profile():
            return
        if view == View.ADMIN:
            try:
                self.admin_page.refresh()
            except ApplicationError as error:
                self.statusBar().showMessage(str(error), 5000)
                self._sync_session()
                return
        self.navigation.navigate(view)
        self._show_scenario()
        self._render()

    def _back(self) -> None:
        if not self.navigation.can_go_back or not self.scenario_page.can_leave():
            return
        self.account_page.clear()
        self.navigation.back()
        if self.navigation.current == View.PROFILE and not self._refresh_profile():
            return
        self._show_scenario()
        self._render()

    def _forward(self) -> None:
        if not self.navigation.can_go_forward or not self.scenario_page.can_leave():
            return
        self.account_page.clear()
        self.navigation.forward()
        if self.navigation.current == View.PROFILE and not self._refresh_profile():
            return
        self._show_scenario()
        self._render()

    def _filter_catalog(self) -> None:
        query = self.search.text().casefold().strip()
        for index in range(self.scenario_list.count()):
            item = self.scenario_list.item(index)
            item.setHidden(
                query not in item.toolTip().casefold()
                or item.data(Qt.ItemDataRole.UserRole + 1)
                != self.archive_filter.isChecked()
            )

    def _archive_filter_changed(self, checked: bool) -> None:
        if not self.scenario_page.can_leave():
            with QSignalBlocker(self.archive_filter):
                self.archive_filter.setChecked(not checked)
            return
        self._filter_catalog()

    def _refresh_catalog(self, user) -> None:
        permitted = user is not None and user.role != Role.LEARNER
        self.search.setEnabled(permitted)
        self.archive_filter.setEnabled(permitted)
        self.new_scenario_button.setEnabled(permitted)
        rows = self.scenarios.catalog(self._token, archived=None) if permitted else ()
        if rows != self._catalog:
            self._catalog = rows
            with QSignalBlocker(self.scenario_list):
                self.scenario_list.clear()
                for scenario in rows:
                    item = QListWidgetItem(
                        scenario.name + (" · Архів" if scenario.archived else "")
                    )
                    item.setData(Qt.ItemDataRole.UserRole, scenario.id)
                    item.setData(Qt.ItemDataRole.UserRole + 1, scenario.archived)
                    item.setToolTip(
                        f"{scenario.name}\n{scenario.parameters.topic}\n{scenario.status.label}"
                        + ("\nАрхівовано" if scenario.archived else "\nАктивний")
                    )
                    self.scenario_list.addItem(item)
                    if scenario.id == self.selected_scenario_id:
                        self.scenario_list.setCurrentItem(item)
            self._filter_catalog()
        if self.selected_scenario_id is not None:
            current = next(
                (row for row in rows if row.id == self.selected_scenario_id), None
            )
            if current is not None:
                self.scenario_page.observe(current)
        if self.selected_scenario_id is not None and not any(
            row.id == self.selected_scenario_id for row in rows
        ):
            self.selected_scenario_id = None
            self.scenario_page.clear()
        self.catalog_title.setText("Сценарії" if rows else "Сценаріїв поки немає")
        self.catalog_hint.setText(
            "Виберіть сценарій у каталозі."
            if rows
            else "Створіть перший сценарій у Конструкторі."
            if permitted
            else "Навчальні сценарії з’являться після їх публікації."
            if user
            else "Увійдіть до облікового запису, щоб побачити ваші сценарії."
        )
        if user is None:
            self.catalog_title.setText("Каталог недоступний")

    def _new_scenario(self) -> None:
        if self.navigation.current != View.CONSTRUCTOR or not self._allowed(
            View.CONSTRUCTOR
        ):
            return
        if not self.scenario_page.can_leave():
            return
        self.selected_scenario_id = None
        with QSignalBlocker(self.scenario_list):
            self.scenario_list.setCurrentRow(-1)
        self.scenario_page.new()

    def _select_scenario(self, item, previous=None) -> None:
        if item is None:
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        if not self.scenario_page.can_leave():
            with QSignalBlocker(self.scenario_list):
                self.scenario_list.setCurrentRow(
                    next(
                        (
                            i
                            for i in range(self.scenario_list.count())
                            if self.scenario_list.item(i).data(Qt.ItemDataRole.UserRole)
                            == self.selected_scenario_id
                        ),
                        -1,
                    )
                )
            return
        self.selected_scenario_id = scenario_id
        self._show_scenario()
        self._select_catalog_id()

    def _scenario_saved(self, scenario: Scenario) -> None:
        self.selected_scenario_id = scenario.id
        self._render()
        self._select_catalog_id()

    def _scenario_archive_changed(self, scenario: Scenario) -> None:
        with QSignalBlocker(self.archive_filter):
            self.archive_filter.setChecked(scenario.archived)
        self._scenario_saved(scenario)
        self._filter_catalog()
        self._show_scenario()

    def _select_catalog_id(self) -> None:
        with QSignalBlocker(self.scenario_list):
            for index in range(self.scenario_list.count()):
                if (
                    self.scenario_list.item(index).data(Qt.ItemDataRole.UserRole)
                    == self.selected_scenario_id
                ):
                    self.scenario_list.setCurrentRow(index)

    def _show_scenario(self) -> None:
        if self.navigation.current == View.ANALYTICS:
            self.analytics_page.set_context(self._token, self.selected_scenario_id)
            return
        self.analytics_page.set_context(None, None)
        if self.navigation.current != View.CONSTRUCTOR:
            return
        if self.selected_scenario_id is None:
            self.scenario_page.clear()
            return
        try:
            scenario = self.scenarios.get(self._token, self.selected_scenario_id)
            actor = self.accounts.current(self._token)
        except ApplicationError as error:
            self.selected_scenario_id = None
            self.scenario_page.clear()
            self.statusBar().showMessage(str(error), 5000)
            return
        self.scenario_page.load(scenario, editable=actor.id == scenario.owner_id)

    def _render(self) -> None:
        current = self.navigation.current
        user = None
        if self._token:
            try:
                user = self.accounts.current(self._token)
            except ApplicationError as error:
                self._signed_out()
                self.statusBar().showMessage(str(error), 5000)
                return
        login_form = current == View.PROFILE and user is None
        self.topbar.setVisible(not login_form)
        self.rail.setVisible(not login_form)
        learner = user is not None and user.role == Role.LEARNER
        for view in (View.CONSTRUCTOR, View.ANALYTICS):
            self.nav_buttons[view].setVisible(user is not None and not learner)
        for view in (View.MY_SCENARIOS, View.MY_RESULTS):
            self.nav_buttons[view].setVisible(learner)
        self.nav_buttons[View.ADMIN].setVisible(
            user is not None and user.role == Role.ADMINISTRATOR
        )
        for view, title in (
            (View.CONSTRUCTOR, "Конструктор"),
            (View.ANALYTICS, "Аналіз"),
        ):
            tooltip = title if user else title + " — перегляд оболонки"
            self.nav_buttons[view].setToolTip(tooltip)
            self.nav_buttons[view].setAccessibleName(tooltip)
        self.badge.setText(
            f"{user.username} · {user.role.label}" if user else "Гостьовий режим"
        )
        self.badge.setMaximumWidth(300)
        self.badge.setToolTip(
            f"{user.display_name} · {user.role.label}" if user else "Гостьовий режим"
        )
        try:
            self._refresh_catalog(user)
        except ApplicationError as error:
            self._signed_out()
            self.statusBar().showMessage(str(error), 5000)
            return
        if current == View.ANALYTICS and self.selected_scenario_id is None:
            self.analytics_page.set_context(None, None)
        self.pages[View.HOME].session_hint.setText(
            (
                "Відкрийте «Мої сценарії» або «Мої результати»."
                if learner
                else (
                    "«+» відкриває Конструктор, іконка графіка — Аналіз. Кнопка "
                    "будинку повертає на Головну."
                )
            )
            if user
            else (
                "«+» відкриває Конструктор, іконка графіка — Аналіз. Кнопка "
                "будинку повертає на Головну.\nУвійдіть, щоб отримати доступ "
                "до ваших сценаріїв."
            )
        )
        for view in (View.HOME, View.ANALYTICS):
            self.pages[view].login_button.setVisible(user is None)
        entering_results = (
            current == View.MY_RESULTS
            and self.workspace.currentWidget() is not self.containers[current]
        )
        self.workspace.setCurrentWidget(self.containers[current])
        self.nav_buttons[current].setChecked(True)
        self.back_button.setEnabled(self.navigation.can_go_back)
        self.forward_button.setEnabled(self.navigation.can_go_forward)
        self.scenario_panel.setVisible(current in (View.CONSTRUCTOR, View.ANALYTICS))
        if learner:
            self.learner_catalog.refresh()
            if entering_results:
                self.learner_history.refresh()
            if (
                current != View.MY_SCENARIOS
                and self.learner_catalog.simulation.controller
            ):
                self.learner_catalog.show_catalog()
        self.new_scenario_button.setVisible(current == View.CONSTRUCTOR)
        self.context_label.setText(
            {
                View.HOME: "Головна",
                View.MY_SCENARIOS: "Мої сценарії",
                View.MY_RESULTS: "Мої результати",
                View.ADMIN: "Адміністрування",
                View.CONSTRUCTOR: "Конструктор",
                View.ANALYTICS: "Аналіз",
                View.SETTINGS: "Налаштування",
                View.PROFILE: "Профіль",
            }[current]
        )
