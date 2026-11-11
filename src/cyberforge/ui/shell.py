"""Main desktop shell. Mode navigation grants no access to scenario data."""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role, Workspace
from cyberforge.groups.service import GroupService
from cyberforge.ui.account_pages import AccountPage
from cyberforge.ui.admin_page import AdminPage
from cyberforge.ui.clipboard_shortcuts import ClipboardShortcuts
from cyberforge.ui.icons import icon
from cyberforge.ui.navigation import AuthenticationState, NavigationState, View
from cyberforge.ui.pages import WorkspacePage, label
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
    def __init__(self, accounts: AccountService) -> None:
        super().__init__()
        self.accounts = accounts
        self.groups = GroupService(accounts)
        self._token: str | None = None
        self.setWindowTitle("CyberForge")
        bounds, minimum = window_geometry(self.screen().availableGeometry())
        self.setMinimumSize(minimum)
        self.setGeometry(bounds)
        self.clipboard_shortcuts = ClipboardShortcuts(self)
        QApplication.instance().installEventFilter(self.clipboard_shortcuts)
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
        self.new_scenario_button.setToolTip(
            "Створення сценаріїв буде доступне після реалізації авторизації "
            "та керування сценаріями."
        )
        catalog.addWidget(self.new_scenario_button)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Пошук сценаріїв")
        self.search.setAccessibleName("Пошук сценаріїв")
        self.search.setEnabled(False)
        self.search.setToolTip(
            "Пошук буде доступний після входу та підключення каталогу."
        )
        catalog.addWidget(self.search)
        catalog.addSpacing(18)
        self.catalog_title = label("Каталог недоступний", "heading")
        catalog.addWidget(self.catalog_title)
        self.catalog_hint = label(
            "Увійдіть до облікового запису, щоб побачити ваші сценарії."
        )
        catalog.addWidget(self.catalog_hint)
        catalog.addStretch()
        catalog.addWidget(label("ПОПЕРЕДНІЙ ПЕРЕГЛЯД", "eyebrow"))
        catalog.addWidget(label("Оболонка інтерфейсу\nБез сценаріїв і результатів"))
        body.addWidget(self.scenario_panel)
        self.workspace = QStackedWidget()
        self.pages: dict[View, WorkspacePage | AccountPage | AdminPage] = {}
        self.containers: dict[View, QScrollArea] = {}
        for view in View:
            if view == View.PROFILE:
                page = AccountPage(self.accounts)
                self.account_page = page
                page.authenticated.connect(self._authenticated)
                page.signed_out.connect(self._signed_out)
                page.close_requested.connect(lambda: self.navigate(View.HOME))
            elif view == View.ADMIN:
                page = AdminPage(
                    self.accounts, self.groups, lambda: self._token, self._sync_session
                )
                self.admin_page = page
            else:
                page = WorkspacePage(view)
                page.profile_requested.connect(lambda: self.navigate(View.PROFILE))
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
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
        self._token = token
        self.authentication_state = AuthenticationState.AUTHENTICATED
        self.navigation.reset()
        self.account_page.refresh(token)
        self._render()

    def _signed_out(self) -> None:
        self.accounts.logout(self._token)
        self._token = None
        self.authentication_state = AuthenticationState.GUEST
        self.navigation.reset()
        self.account_page.refresh(None)
        self.admin_page.clear()
        self.search.clear()
        self._render()

    def _sync_session(self) -> None:
        if self._token:
            try:
                self.accounts.current(self._token)
            except AccessDenied:
                self._signed_out()
            else:
                self._render()

    def _allowed(self, view: View) -> bool:
        if self._token is None:
            return view in (View.HOME, View.PROFILE, View.SETTINGS)
        try:
            self.accounts.current(self._token)
        except AccessDenied:
            self._signed_out()
            return False
        if view.value in {workspace.value for workspace in Workspace}:
            try:
                self.accounts.authorize_workspace(self._token, Workspace(view.value))
            except AccessDenied:
                return False
        return True

    def closeEvent(self, event) -> None:
        self.session_timer.stop()
        self._signed_out()
        super().closeEvent(event)

    def navigate(self, view: View) -> None:
        if not self._allowed(view):
            self.statusBar().showMessage("Доступ заборонено.", 5000)
            self._render()
            return
        if view != View.PROFILE:
            self.account_page.clear()
        if view == View.PROFILE:
            self.account_page.refresh(self._token)
        if view == View.ADMIN:
            try:
                self.admin_page.refresh()
            except ApplicationError as error:
                self.statusBar().showMessage(str(error), 5000)
                self._sync_session()
                return
        self.navigation.navigate(view)
        self._render()

    def _back(self) -> None:
        self.account_page.clear()
        self.navigation.back()
        if self.navigation.current == View.PROFILE:
            self.account_page.refresh(self._token)
        self._render()

    def _forward(self) -> None:
        self.account_page.clear()
        self.navigation.forward()
        if self.navigation.current == View.PROFILE:
            self.account_page.refresh(self._token)
        self._render()

    def _render(self) -> None:
        current = self.navigation.current
        user = None
        if self._token:
            try:
                user = self.accounts.current(self._token)
            except AccessDenied:
                self._signed_out()
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
        self.catalog_title.setText(
            "Сценаріїв поки немає" if user else "Каталог недоступний"
        )
        self.catalog_hint.setText(
            "Навчальні сценарії з’являться після їх публікації."
            if user
            else "Увійдіть до облікового запису, щоб побачити ваші сценарії."
        )
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
        for view in (View.HOME, View.CONSTRUCTOR, View.ANALYTICS):
            self.pages[view].login_button.setVisible(user is None)
        self.workspace.setCurrentWidget(self.containers[current])
        self.nav_buttons[current].setChecked(True)
        self.back_button.setEnabled(self.navigation.can_go_back)
        self.forward_button.setEnabled(self.navigation.can_go_forward)
        self.scenario_panel.setVisible(
            current in (View.CONSTRUCTOR, View.ANALYTICS, View.MY_SCENARIOS)
        )
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
