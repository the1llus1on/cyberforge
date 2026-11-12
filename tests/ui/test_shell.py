"""Guest access boundary, mode routing and desktop layout smoke checks."""

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit
from pytestqt.qtbot import QtBot

from cyberforge.application.accounts import AccountService
from cyberforge.persistence.database import Database
from cyberforge.ui.navigation import AuthenticationState, View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme


@pytest.fixture
def window(qtbot: QtBot, qapp: QApplication, tmp_path) -> Iterator[MainWindow]:
    apply_theme(qapp)
    database = Database(tmp_path / "ui.sqlite3")
    database.upgrade()
    widget = MainWindow(AccountService(database))
    qtbot.addWidget(widget)
    widget.show()
    yield widget
    widget.close()
    database.close()


def test_guest_protected_routes(window):
    for view in (
        View.CONSTRUCTOR,
        View.ANALYTICS,
        View.ADMIN,
        View.MY_SCENARIOS,
        View.MY_RESULTS,
    ):
        assert not window.nav_buttons[view].isVisible()
        window.navigate(view)
        assert window.navigation.current == View.HOME
    assert window.authentication_state == AuthenticationState.GUEST
    window.navigate(View.PROFILE)
    assert window.account_page.password.echoMode() == QLineEdit.EchoMode.Password


@pytest.mark.parametrize("size", [(860, 620), (1280, 800), (1920, 1080)])
@pytest.mark.parametrize("view", [View.HOME, View.PROFILE, View.SETTINGS])
def test_guest_layout(window, size, view, qtbot):
    window.resize(*size)
    window.navigate(view)
    qtbot.wait(10)
    for text in window.pages[view].findChildren(QLabel):
        assert text.height() >= text.heightForWidth(text.width())
