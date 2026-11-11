"""Real login, role navigation, administration, and session cleanup UI paths."""

from secrets import token_urlsafe

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import AccessDenied, Role
from cyberforge.persistence.database import Database
from cyberforge.ui.navigation import AuthenticationState, View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme


@pytest.fixture
def authenticated_window(qtbot, qapp, tmp_path):
    database = Database(tmp_path / "ui.sqlite3")
    database.upgrade()
    accounts = AccountService(database)
    password = token_urlsafe(24)
    accounts.bootstrap("admin", "Адміністратор", password)
    admin = accounts.login("admin", password)
    for name, role in (("teacher", Role.INSTRUCTOR), ("learner", Role.LEARNER)):
        accounts.create_user(admin, name, name, role, password)
    accounts.logout(admin)
    apply_theme(qapp)
    window = MainWindow(accounts)
    qtbot.addWidget(window)
    window.show()
    yield window, password
    window.close()
    database.close()


def login(qtbot, window, username, password):
    window.navigate(View.PROFILE)
    page = window.account_page
    page.username.setText(username)
    page.password.setText(password)
    qtbot.mouseClick(page.login_button, Qt.MouseButton.LeftButton)


@pytest.mark.parametrize(
    "username,role",
    [
        ("admin", Role.ADMINISTRATOR),
        ("teacher", Role.INSTRUCTOR),
        ("learner", Role.LEARNER),
    ],
)
def test_role_login_navigation_logout(qtbot, authenticated_window, username, role):
    window, password = authenticated_window
    window.navigate(View.CONSTRUCTOR)
    login(qtbot, window, username, password)
    assert window.authentication_state == AuthenticationState.AUTHENTICATED
    assert window.navigation.current == View.HOME
    assert not window.navigation.can_go_back
    assert not window.account_page.password.text()
    assert role.label in window.badge.text()
    assert window.nav_buttons[View.ADMIN].isVisible() == (role == Role.ADMINISTRATOR)
    learner = role == Role.LEARNER
    assert window.nav_buttons[View.CONSTRUCTOR].isVisible() != learner
    assert window.nav_buttons[View.MY_SCENARIOS].isVisible() == learner
    assert not window.pages[View.HOME].login_button.isVisible()
    hint = window.pages[View.HOME].session_hint.text()
    assert "Увійдіть" not in hint
    for target in (
        (View.MY_SCENARIOS, View.MY_RESULTS)
        if learner
        else (View.CONSTRUCTOR, View.ANALYTICS)
    ):
        window.navigate(target)
        assert window.navigation.current == target
    if role != Role.ADMINISTRATOR:
        before = window.navigation.current
        window.navigate(View.ADMIN)
        assert window.navigation.current == before
        window.admin_page.perform(window.admin_page.save_user)
        assert "заборонено" in window.admin_page.message.text()
    if learner:
        before = window.navigation.current
        window.navigate(View.CONSTRUCTOR)
        assert window.navigation.current == before
    token = window._token
    window.navigate(View.PROFILE)
    qtbot.mouseClick(window.account_page.logout_button, Qt.MouseButton.LeftButton)
    assert window.navigation.current == View.HOME
    assert window.authentication_state == AuthenticationState.GUEST
    assert not window.navigation.can_go_back
    assert window.admin_page.users.count() == 0
    assert not window.account_page.username.text()
    with pytest.raises(AccessDenied):
        window.accounts.current(token)


def test_wrong_password_then_change(qtbot, authenticated_window):
    window, password = authenticated_window
    login(qtbot, window, "learner", "incorrect")
    assert window.navigation.current == View.PROFILE
    assert "Невірний" in window.account_page.error.text()
    assert not window.account_page.password.text()
    login(qtbot, window, "learner", password)
    window.navigate(View.PROFILE)
    replacement = token_urlsafe(24)
    window.account_page.password.setText(password)
    window.account_page.new_password.setText(replacement)
    qtbot.mouseClick(window.account_page.change_button, Qt.MouseButton.LeftButton)
    assert window.authentication_state == AuthenticationState.GUEST
    assert not window.account_page.new_password.text()
    login(qtbot, window, "learner", replacement)
    assert window.authentication_state == AuthenticationState.AUTHENTICATED


def test_admin_users_groups_membership_and_reset(qtbot, authenticated_window):
    window, password = authenticated_window
    login(qtbot, window, "admin", password)
    window.navigate(View.ADMIN)
    page = window.admin_page
    assert page.users.count() == 3
    page.username.setText("created")
    page.display_name.setText("Новий учень")
    page.role.setCurrentIndex(page.role.findData(Role.LEARNER))
    replacement = token_urlsafe(24)
    page.password.setText(replacement)
    page.perform(page.save_user)
    assert page.users.count() == 4
    assert not page.password.text()
    page.group_name.setText("Навчальна група")
    page.perform(page.save_group)
    assert page.group_list.count() == 1
    page.instructors.item(0).setCheckState(Qt.CheckState.Checked)
    page.learners.item(0).setCheckState(Qt.CheckState.Checked)
    page.perform(page.save_members)
    group = window.groups.list_groups(window._token)[0]
    assert len(group.instructors) == 1 and len(group.learners) == 1
    page.group_list.setCurrentRow(0)
    page.group_name.setText("Оновлена група")
    page.perform(page.save_group)
    assert window.groups.list_groups(window._token)[0].name == "Оновлена група"
    page.users.setCurrentRow(3)
    page.password.setText(token_urlsafe(24))
    page.perform(page.reset_password)
    assert "збережено" in page.message.text()
    assert not page.password.text()


def test_revocation_cleans_visible_admin_data(qtbot, authenticated_window):
    window, password = authenticated_window
    login(qtbot, window, "admin", password)
    window.navigate(View.ADMIN)
    old_token = window._token
    assert window.admin_page.users.count() == 3
    account = window.accounts.current(old_token)
    other_token = window.accounts.login("admin", password)
    window.accounts.reset_password(other_token, account.id, token_urlsafe(24))
    qtbot.waitUntil(lambda: window._token is None, timeout=3000)
    assert window.navigation.current == View.HOME
    assert window.admin_page.users.count() == 0
    assert not window.navigation.can_go_back


@pytest.mark.parametrize("size", [(860, 620), (1280, 800), (1920, 1080)])
@pytest.mark.parametrize(
    "username,views",
    [
        ("admin", (View.HOME, View.ADMIN, View.PROFILE)),
        ("teacher", (View.HOME, View.CONSTRUCTOR)),
        ("learner", (View.HOME, View.MY_SCENARIOS, View.MY_RESULTS)),
    ],
)
def test_role_layout(qtbot, authenticated_window, size, username, views):
    window, password = authenticated_window
    window.resize(*size)
    login(qtbot, window, username, password)
    for view in views:
        window.navigate(view)
        qtbot.wait(10)
        assert window.workspace.geometry().right() < window.width()
        assert window.pages[view].width() <= window.containers[view].viewport().width()
        for text in window.pages[view].findChildren(QLabel):
            if text.isVisible() and text.wordWrap():
                assert text.height() >= text.heightForWidth(text.width()), text.text()


def test_switch_user_drops_history_data_and_passwords(qtbot, authenticated_window):
    window, password = authenticated_window
    login(qtbot, window, "admin", password)
    window.navigate(View.ADMIN)
    assert window.admin_page.users.count() == 3
    window.navigate(View.PROFILE)
    qtbot.mouseClick(window.account_page.logout_button, Qt.MouseButton.LeftButton)
    login(qtbot, window, "learner", password)
    assert not window.navigation.can_go_back
    assert window.admin_page.users.count() == 0
    assert window.account_page.identity.text().endswith("Учень")
    window._back()
    assert window.navigation.current == View.HOME
    window.navigate(View.ADMIN)
    assert window.navigation.current == View.HOME


def test_popup_filters_unicode_and_default(qtbot, authenticated_window):
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtGui import QInputMethodEvent, QKeyEvent
    from PySide6.QtWidgets import QApplication, QLineEdit

    window, password = authenticated_window
    login(qtbot, window, "admin", password)
    window.navigate(View.ADMIN)
    page = window.admin_page
    page.new_user()
    assert page.role.currentData() == Role.LEARNER
    page.role.showPopup()
    qtbot.wait(100)
    index = page.role.model().index(page.role.findData(Role.INSTRUCTOR), 0)
    qtbot.mouseClick(
        page.role.view().viewport(),
        Qt.MouseButton.LeftButton,
        pos=page.role.view().visualRect(index).center(),
    )
    assert page.role.currentData() == Role.INSTRUCTOR
    assert not page.role.view().isVisible()
    page.role.setFocus()
    qtbot.keyClick(page.role, Qt.Key.Key_Home)
    assert page.role.currentData() == Role.ADMINISTRATOR
    qtbot.keyClick(page.role, Qt.Key.Key_End)
    assert page.role.currentData() == Role.LEARNER
    assert len(window.accounts.list_users(window._token)) == 3
    for field in (page.display_name, page.group_name, page.description):
        field.setFocus()
        field.clear()
        for character in "Україна":
            QApplication.sendEvent(
                field,
                QKeyEvent(
                    QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character
                ),
            )
        assert field.text() == "Україна"
        event = QInputMethodEvent()
        event.setCommitString(" Київ")
        QApplication.sendEvent(field, event)
        assert field.text() == "Україна Київ"
    page.learners.item(0).setCheckState(Qt.CheckState.Checked)
    page.users.setCurrentRow(0)
    selected = page.user_id
    for field in page.findChildren(QLineEdit):
        if field.placeholderText().startswith("Пошук"):
            field.setText("невідповідність")
            field.clear()
    assert page.user_id == selected
    assert page.learners.item(0).checkState() == Qt.CheckState.Checked
    page.display_name.setFocus()
    assert page.users.currentItem() is not None
    qtbot.mouseClick(
        page.users.viewport(),
        Qt.MouseButton.LeftButton,
        pos=page.users.viewport().rect().bottomRight() - QPoint(10, 10),
    )
    assert page.user_id is None
    assert not page.users.selectedItems()


def test_deletion_confirmation(qtbot, authenticated_window):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    window, password = authenticated_window
    login(qtbot, window, "admin", password)
    window.navigate(View.ADMIN)
    page = window.admin_page
    page.users.setCurrentRow(2)

    def respond(accept):
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        for button in dialog.buttons():
            if button.text() == ("Видалити" if accept else "Скасувати"):
                button.click()

    QTimer.singleShot(20, lambda: respond(False))
    page.delete_user()
    assert len(window.accounts.list_users(window._token)) == 3
    QTimer.singleShot(20, lambda: respond(True))
    page.delete_user()
    assert len(window.accounts.list_users(window._token)) == 2
