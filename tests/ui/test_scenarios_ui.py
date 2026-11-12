"""Constructor/catalog workflow, read-only modes, and unsaved-edit decisions."""

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox

from cyberforge.ui.navigation import View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme


@pytest.fixture
def scenario_window(qtbot, qapp, scenario_env):
    if not qapp.styleSheet():
        apply_theme(qapp)
    window = MainWindow(scenario_env.accounts)
    # pytest-qt closes widgets before fixture finalizers run. Clear only during
    # harness cleanup so a deliberately dirty test cannot open a modal dialog.
    qtbot.addWidget(
        window, before_close_func=lambda widget: widget.scenario_page.clear()
    )
    window.show()
    window._authenticated(scenario_env.tokens["teacher"])
    window.navigate(View.CONSTRUCTOR)
    yield window


def create(window, topic="Синтетична ситуація"):
    window._new_scenario()
    window.scenario_page.topic.setPlainText(topic)
    assert window.scenario_page.save()
    return window.scenario_page.scenario


def test_constructor_create_edit_search_and_modes(qtbot, scenario_window, scenario_env):
    window = scenario_window
    assert window.new_scenario_button.isEnabled()
    qtbot.mouseClick(window.new_scenario_button, Qt.MouseButton.LeftButton)
    page = window.scenario_page
    assert window.scenario_list.count() == 0
    assert not page.save()
    assert "Некоректні" in page.message.text()
    page.topic.setPlainText("Синтетична ситуація")
    page.audience.setText("Навчальна група")
    page.learning_objective.setPlainText("Перевіряти відправника")
    page.tactics.setPlainText("Терміновість\nАвторитет")
    page.generation_parameters.setPlainText('{"language": "uk"}')
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    saved = page.scenario
    assert saved is not None and not page.dirty
    assert window.scenario_list.count() == 1
    assert window.scenario_list.item(0).text() == saved.name
    assert window.selected_scenario_id == saved.id
    window.search.setText("синтетична")
    assert not window.scenario_list.item(0).isHidden()
    window.search.setText("відсутня тема")
    assert window.scenario_list.item(0).isHidden()
    assert window.selected_scenario_id == saved.id
    window.search.clear()
    page.description.setPlainText("Уточнення")
    assert page.save() and page.scenario.revision == 2
    catalog = window.scenario_list
    window.navigate(View.ANALYTICS)
    assert window.scenario_list is catalog
    assert not window.new_scenario_button.isVisible()
    assert str(saved.id) in window.pages[View.ANALYTICS].scenario_info.text()
    assert (
        "Дані для аналізу відсутні" in window.pages[View.ANALYTICS].scenario_info.text()
    )
    window._back()
    assert window.navigation.current == View.CONSTRUCTOR
    assert (
        page.scenario.id == saved.id and page.description.toPlainText() == "Уточнення"
    )
    window._forward()
    assert window.navigation.current == View.ANALYTICS
    assert len(scenario_env.service.catalog(scenario_env.tokens["teacher"])) == 1


@pytest.mark.parametrize(
    "action", ["mode", "home", "back", "new", "select", "close", "revert"]
)
def test_cancel_protects_unsaved_changes(scenario_window, monkeypatch, action):
    window = scenario_window
    create(window, "Перший")
    second = create(window, "Другий")
    page = window.scenario_page
    page.topic.setPlainText("Незбережена тема")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    if action == "mode":
        window.navigate(View.ANALYTICS)
    elif action == "home":
        window.navigate(View.HOME)
    elif action == "back":
        window._back()
    elif action == "new":
        window._new_scenario()
    elif action == "select":
        window.scenario_list.setCurrentRow(1)
    elif action == "close":
        assert not window.close()
        assert window.session_timer.isActive()
    else:
        page.revert()
    assert window.navigation.current == View.CONSTRUCTOR
    assert window.selected_scenario_id == second.id
    assert page.scenario.id == second.id
    assert page.dirty and page.topic.toPlainText() == "Незбережена тема"
    assert (
        window.scenario_list.currentItem().data(Qt.ItemDataRole.UserRole) == second.id
    )


def test_save_decision_creates_new_record_then_navigates(scenario_window, monkeypatch):
    window = scenario_window
    page = window.scenario_page
    window._new_scenario()
    page.topic.setPlainText("Нова синтетична тема")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Save)
    window.navigate(View.ANALYTICS)
    assert page.scenario.id == window.selected_scenario_id
    assert window.navigation.current == View.ANALYTICS
    assert not page.dirty and window.scenario_list.count() == 1


def test_forward_and_revocation_guard(scenario_window, monkeypatch, scenario_env):
    window = scenario_window
    create(window)
    window.navigate(View.ANALYTICS)
    window._back()
    page = window.scenario_page
    page.topic.setPlainText("Правка перед Вперед")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    window._forward()
    assert window.navigation.current == View.CONSTRUCTOR and page.dirty
    actor = window.accounts.current(window._token)
    window.accounts.reset_password(
        scenario_env.tokens["admin"], actor.id, "synthetic-new-password-123"
    )
    window._sync_session()
    assert window._token is None and not page.dirty
    assert window.selected_scenario_id is None and window.scenario_list.count() == 0


def test_failed_save_prevents_navigation_and_keeps_invalid_input(
    scenario_window, monkeypatch
):
    window = scenario_window
    create(window)
    page = window.scenario_page
    page.topic.setPlainText(" ")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Save)
    window.navigate(View.HOME)
    assert window.navigation.current == View.CONSTRUCTOR
    assert page.dirty and page.topic.toPlainText() == " "
    page.topic.setPlainText("Валідна тема")
    page.generation_parameters.setPlainText("{invalid json")
    assert not page.save() and page.dirty


def test_discard_does_not_write_or_allocate_id(scenario_window, monkeypatch):
    window = scenario_window
    page = window.scenario_page
    saved = create(window)
    page.topic.setPlainText("Відкинута тема")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    window.navigate(View.ANALYTICS)
    assert page.topic.toPlainText() == saved.parameters.topic
    assert window.scenarios.get(window._token, saved.id) == saved
    window.navigate(View.CONSTRUCTOR)
    window._new_scenario()
    page.topic.setPlainText("Нова незбережена")
    window.navigate(View.HOME)
    assert window.scenario_list.count() == 1
    assert not page.dirty


def test_selection_after_save_guard_survives_catalog_rebuild(
    scenario_window, monkeypatch
):
    window = scenario_window
    first = create(window, "Перший")
    second = create(window, "Другий")
    page = window.scenario_page
    page.topic.setPlainText("Другий оновлено")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Save)
    window.scenario_list.setCurrentRow(1)
    assert page.scenario.id == first.id
    assert window.selected_scenario_id == first.id
    assert window.scenario_list.currentItem().data(Qt.ItemDataRole.UserRole) == first.id
    assert (
        window.scenarios.get(window._token, second.id).parameters.topic
        == "Другий оновлено"
    )


def test_stale_editor_and_timer_preserve_changes(scenario_window):
    window = scenario_window
    saved = create(window)
    page = window.scenario_page
    page.topic.setPlainText("Моя правка")
    window.scenarios.update(
        window._token,
        saved.id,
        saved.parameters.model_dump() | {"topic": "Інший редактор"},
        expected_version=1,
        expected_revision=1,
    )
    window._sync_session()
    assert page.topic.toPlainText() == "Моя правка"
    assert not page.save()
    assert "уже змінено" in page.message.text() and page.dirty


def test_logout_clears_catalog_editor_and_analytics(scenario_window, scenario_env):
    window = scenario_window
    create(window)
    window.navigate(View.ANALYTICS)
    window._signed_out()
    assert window.scenario_list.count() == 0
    assert window.selected_scenario_id is None
    assert window.scenario_page.scenario is None
    assert not window.scenario_page.topic.toPlainText()
    assert "Сценарій не вибрано" in window.pages[View.ANALYTICS].scenario_info.text()
    window._authenticated(scenario_env.tokens["other"])
    window.navigate(View.CONSTRUCTOR)
    assert window.scenario_list.count() == 0
    window._signed_out()
    window._authenticated(scenario_env.tokens["admin"])
    window.navigate(View.CONSTRUCTOR)
    window.scenario_list.setCurrentRow(0)
    assert not window.scenario_page.editable
    window.scenario_page.tabs.setCurrentIndex(1)
    assert window.scenario_page.tabs.currentIndex() == 1
    assert window.scenario_page.topic.isReadOnly()
    assert window.scenario_page.generation_parameters.isReadOnly()
    assert not window.scenario_page.save_button.isEnabled()
    assert not window.scenario_page.save()


def test_real_unsaved_dialog_is_localized_and_cancel_default(scenario_window):
    page = scenario_window.scenario_page
    create(scenario_window)
    page.topic.setPlainText("Правка")

    def dismiss():
        box = page.findChild(QMessageBox)
        assert box.defaultButton().text() == "Залишитися"
        assert {b.text() for b in box.buttons()} == {
            "Зберегти",
            "Відкинути зміни",
            "Залишитися",
        }
        box.button(QMessageBox.StandardButton.Cancel).click()

    QTimer.singleShot(0, dismiss)
    assert not page.can_leave()


@pytest.mark.parametrize("size", [(1100, 720), (1400, 900)])
def test_form_actions_and_internal_scroll(qtbot, scenario_window, size):
    window = scenario_window
    create(window)
    window.resize(*size)
    page = window.scenario_page
    for index in range(page.tabs.count()):
        page.tabs.setCurrentIndex(index)
        qtbot.wait(20)
        viewport = window.containers[View.CONSTRUCTOR].viewport()
        for control in (page.save_button, page.revert_button):
            assert viewport.rect().contains(
                control.mapTo(viewport, control.rect().topLeft())
            )
            assert viewport.rect().contains(
                control.mapTo(viewport, control.rect().bottomRight())
            )
        scroll = page.tabs.widget(index)
        assert scroll.widget().width() <= scroll.viewport().width()
