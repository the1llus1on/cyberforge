"""Guest access boundary, mode routing and desktop layout smoke checks."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit
from pytestqt.qtbot import QtBot

from cyberforge.ui.navigation import AuthenticationState, View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme


@pytest.fixture
def window(qtbot: QtBot, qapp: QApplication) -> MainWindow:
    apply_theme(qapp)
    widget = MainWindow()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def click(qtbot: QtBot, window: MainWindow, view: View) -> None:
    qtbot.mouseClick(window.nav_buttons[view], Qt.MouseButton.LeftButton)


def test_guest_start_and_profile(qtbot: QtBot, window: MainWindow) -> None:
    assert window.navigation.current == View.HOME
    assert window.authentication_state == AuthenticationState.GUEST
    assert not window.scenario_panel.isVisible()
    assert "Вітаємо" in window.pages[View.HOME].title.text()
    assert not window.back_button.isEnabled()
    assert not window.forward_button.isEnabled()
    assert not window.new_scenario_button.isVisible()
    qtbot.mouseClick(window.pages[View.HOME].login_button, Qt.MouseButton.LeftButton)
    assert window.navigation.current == View.PROFILE
    assert window.nav_buttons[View.PROFILE].isChecked()
    assert not window.pages[View.PROFILE].findChildren(QLineEdit)


def test_mode_switches_share_catalog_without_granting_access(
    qtbot: QtBot, window: MainWindow
) -> None:
    panel = window.scenario_panel
    for view in (View.CONSTRUCTOR, View.ANALYTICS, View.CONSTRUCTOR):
        click(qtbot, window, view)
        assert window.navigation.current == view
        assert window.scenario_panel is panel
        assert panel.isVisible()
        assert window.authentication_state == AuthenticationState.GUEST
        assert window.workspace.currentWidget() is window.containers[view]
        assert window.nav_buttons[view].isChecked()
        assert sum(b.isChecked() for b in window.nav_buttons.values()) == 1
        assert window.new_scenario_button.isVisible() == (view == View.CONSTRUCTOR)
        assert not window.new_scenario_button.isEnabled()
        assert not window.search.isEnabled()
        assert any(
            "попередній перегляд" in text.text().lower()
            for text in window.pages[view].findChildren(QLabel)
        )
    qtbot.mouseClick(window.new_scenario_button, Qt.MouseButton.LeftButton)
    assert window.navigation.current == View.CONSTRUCTOR


def test_back_forward_and_settings(qtbot: QtBot, window: MainWindow) -> None:
    click(qtbot, window, View.CONSTRUCTOR)
    click(qtbot, window, View.ANALYTICS)
    qtbot.mouseClick(window.back_button, Qt.MouseButton.LeftButton)
    assert window.navigation.current == View.CONSTRUCTOR
    assert window.new_scenario_button.isVisible()
    qtbot.mouseClick(window.forward_button, Qt.MouseButton.LeftButton)
    assert window.navigation.current == View.ANALYTICS
    qtbot.mouseClick(window.back_button, Qt.MouseButton.LeftButton)
    click(qtbot, window, View.SETTINGS)
    assert not window.forward_button.isEnabled()
    assert window.navigation.current == View.SETTINGS


@pytest.mark.parametrize("size", [(860, 620), (1280, 800), (1920, 1080)])
@pytest.mark.parametrize("view", list(View))
def test_layout_does_not_clip_text(
    qtbot: QtBot, window: MainWindow, size: tuple[int, int], view: View
) -> None:
    window.resize(*size)
    click(qtbot, window, view)
    qtbot.waitUntil(lambda: window.workspace.width() > 400)
    QApplication.processEvents()
    assert window.workspace.geometry().right() < window.width()
    assert window.pages[view].width() <= window.containers[view].viewport().width()
    assert window.scenario_panel.isVisible() == (
        view in (View.CONSTRUCTOR, View.ANALYTICS)
    )
    for text in window.pages[view].findChildren(QLabel):
        assert text.height() >= text.heightForWidth(text.width()), text.text()


def test_keyboard_mode_switch(qtbot: QtBot, window: MainWindow) -> None:
    window.nav_buttons[View.ANALYTICS].setFocus()
    qtbot.keyClick(window.nav_buttons[View.ANALYTICS], Qt.Key.Key_Space)
    assert window.navigation.current == View.ANALYTICS


def test_home_content_and_primary_navigation(qtbot: QtBot, window: MainWindow) -> None:
    texts = [text.text() for text in window.pages[View.HOME].findChildren(QLabel)]
    assert "Навчальний цикл" in texts
    assert "Сценарій → Електронний лист → Вебсайт → Аналіз" in texts
    assert any("Конструктор" in text and "Головну" in text for text in texts)
    primary = [
        window.nav_buttons[view]
        for view in (View.HOME, View.CONSTRUCTOR, View.ANALYTICS)
    ]
    assert [control.y() for control in primary] == sorted(
        control.y() for control in primary
    )
    assert all(control.isEnabled() and control.accessibleName() for control in primary)
    for page in window.pages.values():
        assert all(
            "Лише синтетичні навчальні матеріали. Без реальних атак." not in text.text()
            for text in page.findChildren(QLabel)
        )


def test_home_roundtrip_preserves_mode_history_and_guest_state(
    qtbot: QtBot, window: MainWindow
) -> None:
    panel = window.scenario_panel
    click(qtbot, window, View.CONSTRUCTOR)
    click(qtbot, window, View.ANALYTICS)
    window.nav_buttons[View.HOME].setFocus()
    qtbot.keyClick(window.nav_buttons[View.HOME], Qt.Key.Key_Space)
    assert window.navigation.current == View.HOME
    assert window.nav_buttons[View.HOME].isChecked()
    assert not panel.isVisible()
    qtbot.mouseClick(window.back_button, Qt.MouseButton.LeftButton)
    assert window.navigation.current == View.ANALYTICS
    assert panel.isVisible()
    assert window.scenario_panel is panel
    qtbot.mouseClick(window.forward_button, Qt.MouseButton.LeftButton)
    assert window.navigation.current == View.HOME
    assert not panel.isVisible()
    assert window.authentication_state == AuthenticationState.GUEST
    assert not window.new_scenario_button.isEnabled()
    assert not window.search.isEnabled()
