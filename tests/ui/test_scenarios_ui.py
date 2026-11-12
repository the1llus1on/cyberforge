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
    monkeypatch.setattr(page, "confirm_revert", lambda: False)
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


def test_archive_restore_catalog_and_shared_identity(
    qtbot, scenario_window, monkeypatch
):
    window = scenario_window
    create(window, "Активний запис")
    saved = create(window, "Архівний приклад")
    page = window.scenario_page
    monkeypatch.setattr(page, "confirm_archive", lambda: True)
    qtbot.mouseClick(page.archive_button, Qt.MouseButton.LeftButton)
    assert page.scenario.archived and not page.editable
    assert page.topic.isReadOnly() and not page.save()
    assert window.archive_filter.isChecked()
    assert sum(not window.scenario_list.item(i).isHidden() for i in range(2)) == 1
    window.search.setText("архівовано")
    assert not window.scenario_list.currentItem().isHidden()
    window.search.setText("неіснуючий")
    assert window.scenario_list.currentItem().isHidden()
    window.search.clear()
    window.navigate(View.ANALYTICS)
    assert window.selected_scenario_id == saved.id
    assert "Архівовано" in window.pages[View.ANALYTICS].scenario_info.text()
    window.navigate(View.CONSTRUCTOR)
    qtbot.mouseClick(page.restore_button, Qt.MouseButton.LeftButton)
    assert page.editable and not page.scenario.archived
    assert not window.archive_filter.isChecked()
    assert (page.scenario.id, page.scenario.version, page.scenario.revision) == (
        saved.id,
        1,
        1,
    )
    assert page.scenario.archive_revision == 2
    assert sum(not window.scenario_list.item(i).isHidden() for i in range(2)) == 2


@pytest.mark.parametrize("decision", ["Save", "Discard", "Cancel"])
def test_archive_unsaved_decisions(scenario_window, monkeypatch, decision):
    window = scenario_window
    original = create(window)
    page = window.scenario_page
    page.topic.setPlainText("Незбережена правка")
    monkeypatch.setattr(page, "confirm_archive", lambda: True)
    monkeypatch.setattr(
        page, "ask_unsaved", lambda: getattr(QMessageBox.StandardButton, decision)
    )
    assert page.archive() == (decision != "Cancel")
    saved = window.scenarios.get(window._token, original.id)
    assert saved.archived == (decision != "Cancel")
    assert saved.parameters.topic == (
        "Незбережена правка" if decision == "Save" else original.parameters.topic
    )
    if decision == "Cancel":
        assert page.dirty and page.topic.toPlainText() == "Незбережена правка"


def test_declined_archive_confirmation_does_not_touch_edits(
    scenario_window, monkeypatch
):
    window = scenario_window
    original = create(window)
    page = window.scenario_page
    page.topic.setPlainText("Моя правка")
    monkeypatch.setattr(page, "confirm_archive", lambda: False)
    assert not page.archive()
    assert page.dirty and page.topic.toPlainText() == "Моя правка"
    assert window.scenarios.get(window._token, original.id) == original


def test_archive_filter_guard_and_revert_match_labels(scenario_window, monkeypatch):
    window = scenario_window
    original = create(window)
    page = window.scenario_page
    page.topic.setPlainText("Моя правка")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    window.archive_filter.setChecked(True)
    assert not window.archive_filter.isChecked() and page.dirty
    monkeypatch.setattr(page, "confirm_revert", lambda: False)
    page.revert()
    assert page.dirty
    monkeypatch.setattr(page, "confirm_revert", lambda: True)
    page.revert()
    assert not page.dirty and page.topic.toPlainText() == original.parameters.topic
    assert window.scenarios.get(window._token, original.id) == original


def test_invalid_and_stale_saves_block_archive(scenario_window, monkeypatch):
    window = scenario_window
    original = create(window)
    page = window.scenario_page
    monkeypatch.setattr(page, "confirm_archive", lambda: True)
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Save)
    page.generation_parameters.setPlainText("{invalid")
    assert not page.archive() and page.dirty
    assert not window.scenarios.get(window._token, original.id).archived
    page.generation_parameters.setPlainText("{}")
    page.topic.setPlainText("Локальна правка")
    window.scenarios.update(
        window._token,
        original.id,
        original.parameters.model_dump() | {"topic": "Зовнішня правка"},
        expected_version=1,
        expected_revision=1,
    )
    assert not page.archive()
    assert page.dirty and page.topic.toPlainText() == "Локальна правка"
    assert not window.scenarios.get(window._token, original.id).archived


def test_archived_foreign_record_is_inspectable_but_not_mutable(
    scenario_window, scenario_env
):
    window = scenario_window
    original = create(window)
    archived = window.scenarios.archive(
        window._token,
        original.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=0,
    )
    window._signed_out()
    window._authenticated(scenario_env.tokens["other"])
    window.navigate(View.CONSTRUCTOR)
    window.archive_filter.setChecked(True)
    assert window.scenario_list.count() == 0
    window._signed_out()
    window._authenticated(scenario_env.tokens["admin"])
    window.navigate(View.CONSTRUCTOR)
    assert window.scenario_list.item(0).isHidden()
    window.archive_filter.setChecked(True)
    window.scenario_list.setCurrentRow(0)
    page = window.scenario_page
    assert page.scenario == archived and not page.owned
    assert not page.archive_button.isVisible() and not page.restore_button.isVisible()
    page.tabs.setCurrentIndex(1)
    assert page.nist_cues.isEnabled()
    assert all(
        not page.nist_cues.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable
        for i in range(page.nist_cues.count())
    )
    assert not page.archive() and not page.restore()


def test_external_archive_retains_edits_and_rejects_archive_restore_aba(
    scenario_window,
):
    window = scenario_window
    original = create(window)
    page = window.scenario_page
    page.topic.setPlainText("Для ручного відновлення")
    archived = window.scenarios.archive(
        window._token,
        original.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=0,
    )
    window._sync_session()
    assert page.dirty and page.topic.isReadOnly()
    assert page.topic.toPlainText() == "Для ручного відновлення"
    window.scenarios.restore(
        window._token,
        original.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=archived.archive_revision,
    )
    window._sync_session()
    assert page.dirty and not page.save()
    assert "уже змінено" in page.message.text()
    assert page.topic.toPlainText() == "Для ручного відновлення"


def test_independent_windows_keep_losing_editor_buffer(
    qtbot, scenario_window, scenario_env
):
    from pathlib import Path

    from cyberforge.application.accounts import AccountService
    from cyberforge.persistence.database import Database

    first = scenario_window
    saved = create(first)
    database = Database(Path(scenario_env.database.engine.url.database))
    accounts = AccountService(database)
    other = MainWindow(accounts)
    qtbot.addWidget(
        other, before_close_func=lambda widget: widget.scenario_page.clear()
    )
    try:
        other.show()
        other._authenticated(accounts.login("teacher", scenario_env.password))
        other.navigate(View.CONSTRUCTOR)
        other.scenario_list.setCurrentRow(0)
        other.scenario_page.topic.setPlainText("Правка другого вікна")
        first.scenario_page.topic.setPlainText("Збереження першого вікна")
        assert first.scenario_page.save()
        assert not other.scenario_page.save()
        assert other.scenario_page.dirty
        assert other.scenario_page.topic.toPlainText() == "Правка другого вікна"
        assert (
            first.scenarios.get(first._token, saved.id).parameters.topic
            == "Збереження першого вікна"
        )
    finally:
        other.scenario_page.clear()
        other.close()
        database.close()


def test_cue_selector_keyboard_save_and_reopen(qtbot, scenario_window):
    window = scenario_window
    window._new_scenario()
    page = window.scenario_page
    page.topic.setPlainText("Бажані ознаки листа")
    page.tabs.setCurrentIndex(1)
    picker = page.nist_cues
    picker.setFocus()
    picker.setCurrentRow(0)
    qtbot.keyClick(picker, Qt.Key.Key_Space)
    picker.setCurrentRow(22)
    qtbot.keyClick(picker, Qt.Key.Key_Space)
    assert tuple(picker.selected()) == ("B.1.1", "B.5.6")
    assert page.save()
    saved = page.scenario
    window.navigate(View.ANALYTICS)
    window.navigate(View.CONSTRUCTOR)
    assert picker.selected() == saved.parameters.nist_cues
    assert "Spelling and grammar irregularities" in picker.item(0).toolTip()


def test_legacy_cues_visible_and_preserved(scenario_window):
    import json

    from sqlalchemy import text

    window = scenario_window
    saved = create(window)
    with window.accounts.database.engine.begin() as db:
        db.execute(
            text("UPDATE scenario_versions SET parameters=:p WHERE scenario_id=:id"),
            dict(
                p=json.dumps(
                    dict(
                        topic="Історична тема",
                        difficulty="beginner",
                        nist_cues=["Довільна ознака"],
                    )
                ),
                id=saved.id,
            ),
        )
    window._show_scenario()
    page = window.scenario_page
    page.tabs.setCurrentIndex(1)
    assert page.legacy_cues.toPlainText() == "Довільна ознака"
    assert page.legacy_cues.isReadOnly() and page.nist_cues.selected() == ()
    page.description.setPlainText("Уточнення")
    assert page.save()
    assert page.scenario.parameters.legacy_nist_cues == ("Довільна ознака",)


@pytest.mark.parametrize("decision", ["Save", "Discard", "Cancel"])
def test_restore_never_silently_discards_external_archive_buffer(
    scenario_window, monkeypatch, decision
):
    window = scenario_window
    original = create(window)
    page = window.scenario_page
    page.topic.setPlainText("Текст для ручного перенесення")
    window.scenarios.archive(
        window._token,
        original.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=0,
    )
    window._sync_session()
    monkeypatch.setattr(
        page, "ask_unsaved", lambda: getattr(QMessageBox.StandardButton, decision)
    )
    assert page.restore() == (decision == "Discard")
    current = window.scenarios.get(window._token, original.id)
    assert current.parameters.topic == original.parameters.topic
    assert current.archived == (decision != "Discard")
    if decision != "Discard":
        assert (
            page.dirty and page.topic.toPlainText() == "Текст для ручного перенесення"
        )


def test_archive_failure_safe_message_and_real_confirmation(
    scenario_window, monkeypatch
):
    from sqlalchemy import text

    window = scenario_window
    original = create(window)
    page = window.scenario_page

    def dismiss():
        box = page.findChild(QMessageBox)
        assert box.defaultButton().text() == "Залишитися"
        box.defaultButton().click()

    QTimer.singleShot(0, dismiss)
    assert not page.archive()
    assert window.scenarios.get(window._token, original.id) == original
    with window.accounts.database.engine.begin() as db:
        db.execute(
            text(
                "CREATE TRIGGER synthetic_failure BEFORE UPDATE ON scenarios "
                "BEGIN SELECT RAISE(ABORT, 'private SQL failure'); END"
            )
        )
    monkeypatch.setattr(page, "confirm_archive", lambda: True)
    assert not page.archive()
    assert page.message.text() and "private SQL" not in page.message.text()
    assert window.scenarios.get(window._token, original.id) == original


def test_constructor_empty_state_has_no_form_actions_or_database_writes(
    qtbot, scenario_window
):
    from PySide6.QtWidgets import QLabel
    from sqlalchemy import event, text

    window = scenario_window
    window.navigate(View.HOME)
    writes = []

    def observe_sql(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in {
            "INSERT",
            "UPDATE",
            "DELETE",
            "REPLACE",
            "CREATE",
            "ALTER",
            "DROP",
        }:
            writes.append(statement)

    engine = window.accounts.database.engine
    event.listen(engine, "before_cursor_execute", observe_sql)
    try:
        qtbot.mouseClick(
            window.nav_buttons[View.CONSTRUCTOR], Qt.MouseButton.LeftButton
        )
        page = window.scenario_page
        assert page.content_stack.currentWidget() == page.empty_state
        assert page.empty_card.isVisible() and not page.editor.isVisible()
        assert any(
            label.text() == "Сценарій не вибрано"
            for label in page.empty_card.findChildren(QLabel)
        )
        for control in (
            page.tabs,
            page.topic,
            page.nist_cues,
            page.save_button,
            page.revert_button,
            page.archive_button,
            page.restore_button,
        ):
            assert not control.isVisible()
        assert window.scenario_list.isVisible()
        assert (
            window.new_scenario_button.isVisible()
            and window.new_scenario_button.isEnabled()
        )
        assert window.selected_scenario_id is None and not page.active
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM scenarios")).scalar() == 0
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM scenario_versions")
                ).scalar()
                == 0
            )
        assert writes == []
    finally:
        event.remove(engine, "before_cursor_execute", observe_sql)


def test_explicit_new_opens_form_without_allocating_id(qtbot, scenario_window):
    window = scenario_window
    page = window.scenario_page
    qtbot.mouseClick(window.new_scenario_button, Qt.MouseButton.LeftButton)
    assert page.content_stack.currentWidget() == page.editor
    assert not page.empty_state.isVisible()
    assert (
        page.tabs.isVisible()
        and page.topic.isVisible()
        and page.save_button.isVisible()
    )
    page.tabs.setCurrentIndex(1)
    assert page.nist_cues.isVisible()
    assert page.active and page.scenario is None and window.selected_scenario_id is None
    assert window.scenarios.catalog(window._token) == ()
    assert not page.save()
    assert window.scenarios.catalog(window._token) == ()
    page.topic.setPlainText("Явно створений синтетичний сценарій")
    assert page.save()
    assert page.scenario.id == window.selected_scenario_id
    assert page.content_stack.currentWidget() == page.editor


@pytest.mark.parametrize("archived", [False, True])
def test_selected_mode_roundtrip_and_plus_preserve_editor_and_archive_filter(
    qtbot, scenario_window, monkeypatch, archived
):
    window = scenario_window
    saved = create(window)
    page = window.scenario_page
    if archived:
        monkeypatch.setattr(page, "confirm_archive", lambda: True)
        assert page.archive()
    window.navigate(View.HOME)
    qtbot.mouseClick(window.nav_buttons[View.CONSTRUCTOR], Qt.MouseButton.LeftButton)
    assert page.content_stack.currentWidget() == page.editor
    assert page.topic.toPlainText() == saved.parameters.topic
    assert page.topic.isReadOnly() == archived
    assert window.archive_filter.isChecked() == archived
    window.navigate(View.ANALYTICS)
    window.navigate(View.CONSTRUCTOR)
    qtbot.mouseClick(window.nav_buttons[View.CONSTRUCTOR], Qt.MouseButton.LeftButton)
    assert window.selected_scenario_id == saved.id and page.scenario.id == saved.id
    assert page.editor.isVisible() and not page.empty_state.isVisible()
    assert window.archive_filter.isChecked() == archived


def test_unselected_new_draft_cancel_then_discard_returns_to_empty_state(
    scenario_window, monkeypatch
):
    window = scenario_window
    window._new_scenario()
    page = window.scenario_page
    page.topic.setPlainText("Незбережена синтетична тема")
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    window.navigate(View.ANALYTICS)
    assert window.navigation.current == View.CONSTRUCTOR
    assert page.dirty and page.editor.isVisible()
    assert page.topic.toPlainText() == "Незбережена синтетична тема"
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    window.navigate(View.ANALYTICS)
    window.navigate(View.CONSTRUCTOR)
    assert page.content_stack.currentWidget() == page.empty_state
    assert not page.active and window.selected_scenario_id is None
    assert window.scenarios.catalog(window._token) == ()


def test_invalid_selection_returns_to_empty_without_changing_saved_data(
    scenario_window,
):
    window = scenario_window
    saved = create(window)
    window.navigate(View.HOME)
    window.selected_scenario_id = 99999
    window.navigate(View.CONSTRUCTOR)
    assert window.selected_scenario_id is None
    assert (
        window.scenario_page.content_stack.currentWidget()
        == window.scenario_page.empty_state
    )
    assert window.scenarios.get(window._token, saved.id) == saved
