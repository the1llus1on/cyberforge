"""Main desktop shell. Mode navigation grants no access to scenario data."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
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

from cyberforge.ui.icons import icon
from cyberforge.ui.navigation import AuthenticationState, NavigationState, View
from cyberforge.ui.pages import WorkspacePage, label


def button(text: str, icon_name: str, tooltip: str) -> QPushButton:
    result = QPushButton(text)
    result.setIcon(icon(icon_name))
    result.setIconSize(QSize(22, 22))
    result.setToolTip(tooltip)
    result.setAccessibleName(tooltip)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CyberForge")
        self.resize(1280, 800)
        self.setMinimumSize(860, 620)
        self.authentication_state = AuthenticationState.GUEST
        self.navigation = NavigationState()
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(root)
        topbar = QFrame()
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
        badge.setObjectName("badge")
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        top.addWidget(badge)
        outer.addWidget(topbar)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)
        rail = QFrame()
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
        catalog.addWidget(label("Каталог недоступний", "heading"))
        catalog.addWidget(
            label("Увійдіть до облікового запису, щоб побачити ваші сценарії.")
        )
        catalog.addStretch()
        catalog.addWidget(label("ПОПЕРЕДНІЙ ПЕРЕГЛЯД", "eyebrow"))
        catalog.addWidget(label("Оболонка інтерфейсу\nБез сценаріїв і результатів"))
        body.addWidget(self.scenario_panel)
        self.workspace = QStackedWidget()
        self.pages: dict[View, WorkspacePage] = {}
        self.containers: dict[View, QScrollArea] = {}
        for view in View:
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
        self._render()

    def navigate(self, view: View) -> None:
        self.navigation.navigate(view)
        self._render()

    def _back(self) -> None:
        self.navigation.back()
        self._render()

    def _forward(self) -> None:
        self.navigation.forward()
        self._render()

    def _render(self) -> None:
        current = self.navigation.current
        self.workspace.setCurrentWidget(self.containers[current])
        self.nav_buttons[current].setChecked(True)
        self.back_button.setEnabled(self.navigation.can_go_back)
        self.forward_button.setEnabled(self.navigation.can_go_forward)
        self.scenario_panel.setVisible(current in (View.CONSTRUCTOR, View.ANALYTICS))
        self.new_scenario_button.setVisible(current == View.CONSTRUCTOR)
        self.context_label.setText(
            {
                View.HOME: "Головна",
                View.CONSTRUCTOR: "Конструктор",
                View.ANALYTICS: "Аналіз",
                View.SETTINGS: "Налаштування",
                View.PROFILE: "Профіль",
            }[current]
        )
