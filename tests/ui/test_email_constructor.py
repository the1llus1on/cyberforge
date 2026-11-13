"""Real Email agent/gateway in a responsive native Qt workspace, without network."""

import json
import socket
from threading import Event, get_ident

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QMessageBox, QPlainTextEdit
from sqlalchemy import text

from cyberforge.application.email_materials import EmailMaterialService, MaterialState
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    Provider,
    ProviderResponse,
)
from cyberforge.llm.factory import create_gateway
from cyberforge.ui.email_source import EmailSourceDialog, render_email_html
from cyberforge.ui.navigation import View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture
def email_window(qtbot, qapp, scenario_env):
    apply_theme(qapp)
    emails = EmailMaterialService(scenario_env.service, create_gateway(), demo=True)
    window = MainWindow(scenario_env.accounts, emails)
    qtbot.addWidget(
        window, before_close_func=lambda widget: widget.scenario_page.clear()
    )
    window.show()
    window._authenticated(scenario_env.tokens["teacher"])
    window.navigate(View.CONSTRUCTOR)
    window._new_scenario()
    window.scenario_page.topic.setPlainText("Навчальне повідомлення українською")
    assert window.scenario_page.save()
    yield window
    qtbot.waitUntil(lambda: not window.scenario_page.email_page.running, timeout=10000)


def open_generated(window, qtbot):
    window.scenario_page.open_email()
    page = window.scenario_page.email_page
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft is not None, page.message.text()
    return page


def test_mail_navigation_source_copy_explicit_save_reopen(email_window, qtbot):
    window = email_window
    card = window.scenario_page
    assert card.email_status.text() == MaterialState.EMPTY
    page = open_generated(window, qtbot)
    assert page.status.text() == MaterialState.UNSAVED
    assert not card.email_material.property("saved")
    assert page.messages.count() == len(page.draft.slots.background) + 1
    assert page.preview.views.currentIndex() == 0
    qtbot.mouseClick(
        page.messages.viewport(),
        Qt.MouseButton.LeftButton,
        pos=page.messages.visualItemRect(page.messages.item(0)).center(),
    )
    assert page.preview.views.currentWidget() == page.preview.reading
    assert page.subject.toPlainText() == page.draft.slots.main.subject
    assert page.body.toPlainText() == page.draft.slots.main.body_text
    assert page.sender.height() >= page.sender.fontMetrics().lineSpacing() * 2
    assert page.timestamp.text() == "09:30 · навчальний час"
    assert not page.messages.item(0).font().bold()
    assert page.messages.item(1).font().bold()
    page.preview.inbox_back.click()
    assert page.preview.views.currentIndex() == 0
    page.messages.setFocus()
    qtbot.keyClick(page.messages, Qt.Key.Key_Down)
    qtbot.keyClick(page.messages, Qt.Key.Key_Return)
    assert page.messages.currentRow() == 1
    assert page.body.toPlainText() == page.draft.slots.background[0].body_text
    assert page.sender.toPlainText().endswith(
        page.draft.slots.background[0].sender_address
    )
    assert not page.messages.item(1).font().bold()
    assert page.timestamp.text() == "09:25 · навчальний час"
    page.body.setFocus()
    qtbot.keyClick(page.body, Qt.Key.Key_Tab)
    assert page.refinement.hasFocus()
    draft = page.draft

    def inspect_dialog():
        dialog = page.findChild(EmailSourceDialog)
        try:
            assert dialog is not None and dialog.isModal()
            assert dialog.source.isReadOnly()
            assert json.loads(dialog.source.toPlainText()) == draft.model_dump(
                mode="json"
            )
            assert dialog.highlighter.document() is dialog.source.document()
            dialog.highlighter.rehighlight()
            assert dialog.source.document().firstBlock().next().layout().formats()
            dialog.copy_button.click()
            assert QApplication.clipboard().text() == dialog.source.toPlainText()
            assert dialog.tabs.count() == 2
            assert "канонічний" in dialog.explanation.text()
            assert "Qt його не використовує" in dialog.explanation.text()
            dialog.tabs.setCurrentIndex(1)
            assert dialog.html_source.isReadOnly()
            html = dialog.html_source.toPlainText()
            assert html == render_email_html(draft, 1)
            assert "<h1>" in html and draft.slots.background[0].subject in html
            qtbot.keyClicks(dialog.html_source, "must-not-edit")
            assert dialog.html_source.toPlainText() == html
            dialog.copy_button.click()
            assert dialog.copy_button.text() == "Копіювати HTML"
            assert QApplication.clipboard().text() == html
        finally:
            if dialog:
                dialog.accept()

    QTimer.singleShot(0, inspect_dialog)
    page.code_button.click()
    assert page.save_button.isEnabled()
    page.save_button.click()
    assert card.content_stack.currentWidget() == card.editor
    assert card.email_status.text() == MaterialState.SAVED
    assert card.email_material.property("saved")
    window.resize(1100, 720)
    qtbot.wait(20)
    viewport = window.containers[View.CONSTRUCTOR].viewport()
    for control in (card.save_button, card.revert_button):
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().topLeft())
        )
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().bottomRight())
        )
    card.open_email()
    assert page.draft == draft and not page.save_button.isEnabled()
    assert page.status.text() == MaterialState.SAVED
    assert window.emails.load(window._token, card.scenario).draft == draft
    assert card.scenario.status == "draft"
    page.preview.open_message(0)
    assert "перехід вимкнено" in page.resource.text()


def test_refinement_new_candidate_never_overwrites_and_failed_save_keeps_it(
    email_window, qtbot, monkeypatch
):
    window = email_window
    page = open_generated(window, qtbot)
    original = page.draft
    assert page.save()
    window.scenario_page.open_email()
    page.preview.open_message(0)
    assert "для перегенерації" in page.refinement_label.text()
    assert "а не пряме редагування" in page.refinement_help.text()
    assert "лише після «Зберегти»" in page.refinement_help.text()
    assert page.generate_button.text() == "Перегенерувати"
    page.refinement.setPlainText("Додай стислий навчальний вступ")
    assert page.body.toPlainText() == original.slots.main.body_text
    assert page.draft == original and not page.unsaved
    assert not page.save_button.isEnabled()
    page.preview.search.setText(original.slots.main.sender_address)
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft != original and page.unsaved
    assert page.draft.provenance == original.provenance
    assert page.preview.search.text() == ""
    assert page.messages.count() == len(page.draft.slots.background) + 1
    workspace = page.workspace
    assert window.emails.load(window._token, workspace.scenario).draft == original

    def fail(*args):
        raise ApplicationError("Тимчасово неможливо зберегти.")

    monkeypatch.setattr(window.emails, "save", fail)
    assert not page.save()
    assert page.unsaved and page.draft != original
    assert "неможливо" in page.message.text()
    assert window.emails.load(window._token, workspace.scenario).draft == original


def test_light_mailbox_search_and_browser_boundary(email_window, qtbot):
    page = open_generated(email_window, qtbot)
    preview = page.preview
    assert "Gmail" in preview.browser_tab.text()
    assert preview.palette().color(QPalette.ColorRole.Window).name() == "#f6f8fc"
    assert preview.body.palette().color(QPalette.ColorRole.Base).name() == "#ffffff"
    assert email_window.palette().color(QPalette.ColorRole.Window).name() == "#191b20"
    assert preview.address.isReadOnly()
    assert "mail.training.invalid" in preview.address.text()
    assert not preview.compose.isEnabled() and not preview.reply.isEnabled()
    before = page.draft.model_dump_json()
    preview.address.setFocus()
    qtbot.keyClick(preview.address, Qt.Key.Key_Return)
    assert page.draft.model_dump_json() == before
    assert preview.views.currentIndex() == 0
    assert not preview.read_messages
    preview.search.setText(page.draft.slots.background[0].sender_address)
    assert preview.messages.item(0).isHidden()
    assert not preview.messages.item(1).isHidden()
    preview.messages.setCurrentRow(1)
    preview.messages.setFocus()
    qtbot.keyClick(preview.messages, Qt.Key.Key_Return)
    assert preview.selected_index == 1
    assert preview.body.toPlainText() == page.draft.slots.background[0].body_text
    assert "participant@training.invalid" in preview.recipient.text()
    preview.inbox_button.click()
    assert preview.views.currentIndex() == 0
    preview.search.clear()
    assert all(
        not preview.messages.item(i).isHidden() for i in range(preview.messages.count())
    )
    assert not preview.messages.item(1).font().bold()


@pytest.mark.parametrize("opened", [False, True])
def test_compact_mailbox_keeps_critical_controls_visible(email_window, qtbot, opened):
    window = email_window
    window.resize(1100, 720)
    page = open_generated(window, qtbot)
    if opened:
        page.preview.open_message(0)
    qtbot.wait(20)
    viewport = window.containers[View.CONSTRUCTOR].viewport()
    for control in (
        page.back_button,
        page.refinement,
        page.code_button,
        page.generate_button,
        page.save_button,
    ):
        assert control.isVisible()
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().topLeft())
        )
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().bottomRight())
        )
    assert window.containers[View.CONSTRUCTOR].horizontalScrollBar().maximum() == 0
    assert page.preview.folders.width() < 60


@pytest.mark.parametrize("choice", ["Save", "Discard", "Cancel"])
def test_unsaved_guard_for_navigation(email_window, qtbot, monkeypatch, choice):
    window = email_window
    page = open_generated(window, qtbot)
    scenario = page.workspace.scenario
    monkeypatch.setattr(
        page, "ask_unsaved", lambda: getattr(QMessageBox.StandardButton, choice)
    )
    window.navigate(View.ANALYTICS)
    assert window.navigation.current == (
        View.CONSTRUCTOR if choice == "Cancel" else View.ANALYTICS
    )
    assert window.emails.load(window._token, scenario).state == (
        MaterialState.SAVED if choice == "Save" else MaterialState.EMPTY
    )
    if choice == "Cancel":
        assert page.unsaved and page.draft is not None


def test_real_unsaved_dialog_defaults_to_stay(email_window, qtbot):
    page = open_generated(email_window, qtbot)

    def dismiss():
        box = page.findChild(QMessageBox)
        assert box.defaultButton().text() == "Залишитися"
        assert any(button.text() == "Зберегти лист" for button in box.buttons())
        box.defaultButton().click()

    QTimer.singleShot(0, dismiss)
    assert not page.can_leave() and page.unsaved


@pytest.mark.parametrize(
    "failure",
    [
        ErrorCategory.TIMEOUT,
        ErrorCategory.SAFETY,
        ErrorCategory.BUDGET,
        ErrorCategory.VALIDATION,
    ],
)
def test_generation_errors_retain_saved_preview(
    email_window, qtbot, monkeypatch, failure
):
    window = email_window
    page = open_generated(window, qtbot)
    draft = page.draft
    assert page.save()
    window.scenario_page.open_email()

    def fail(*args, **kwargs):
        raise GenerationError(failure)

    monkeypatch.setattr(window.emails, "generate", fail)
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft == draft and not page.unsaved
    assert page.status.text() == MaterialState.SAVED
    assert page.message.text()
    assert window.emails.load(window._token, page.workspace.scenario).draft == draft


@pytest.mark.parametrize(
    "action",
    [
        "navigate",
        "scenario",
        "logout",
        "session",
        "version",
        "revision",
        "archive",
        "timeout",
        "close",
    ],
)
def test_delayed_generation_responsive_and_stale_completion_ignored(
    email_window, qtbot, monkeypatch, action, scenario_env
):
    window = email_window
    card, page = window.scenario_page, window.scenario_page.email_page
    release, started = Event(), Event()
    service_generate = window.emails.generate
    calls, execution_threads = [], []

    def delayed(*args, **kwargs):
        calls.append(1)
        execution_threads.append(get_ident())
        started.set()
        if not release.wait(timeout=10):
            raise GenerationError(ErrorCategory.TIMEOUT)
        return service_generate(*args, **kwargs)

    monkeypatch.setattr(window.emails, "generate", delayed)
    try:
        card.open_email()
        qtbot.waitUntil(started.is_set, timeout=5000)
        ticks = []
        QTimer.singleShot(0, lambda: ticks.append(get_ident()))
        qtbot.waitUntil(lambda: bool(ticks), timeout=1000)
        assert execution_threads[0] != get_ident() == ticks[0]
        assert page.progress.isVisible()
        assert page.status.text() == MaterialState.GENERATING
        page.generate()
        assert calls == [1]
        scenario = card.scenario
        if action == "navigate":
            window.navigate(View.HOME)
        elif action == "scenario":
            other = window.scenarios.create(
                window._token, dict(topic="Інший сценарій", difficulty="beginner")
            )
            window._render()
            for i in range(window.scenario_list.count()):
                if (
                    window.scenario_list.item(i).data(Qt.ItemDataRole.UserRole)
                    == other.id
                ):
                    window.scenario_list.setCurrentRow(i)
            assert card.scenario.id == other.id
        elif action == "logout":
            window._signed_out()
        elif action == "session":
            window._authenticated(
                window.accounts.login("teacher", scenario_env.password)
            )
        elif action in ("version", "revision"):
            if action == "version":
                with window.accounts.database.engine.begin() as db:
                    db.execute(text("UPDATE scenario_versions SET status='published'"))
            window.scenarios.update(
                window._token,
                scenario.id,
                scenario.parameters.model_dump() | {"topic": "Нова ревізія"},
                expected_version=1,
                expected_revision=1,
            )
            window._sync_session()
        elif action == "archive":
            window.scenarios.archive(
                window._token,
                scenario.id,
                expected_version=1,
                expected_revision=1,
                expected_archive_revision=0,
            )
            window._sync_session()
        elif action == "timeout":
            page.watchdog.start(1)
            qtbot.waitUntil(lambda: page.pending is None, timeout=1000)
            assert "Доставку" in page.message.text()
        else:
            assert not window.close()
            assert window._closing_pending and window.isVisible()
        release.set()
        qtbot.waitUntil(lambda: not page.running, timeout=10000)
        if action == "close":
            qtbot.waitUntil(lambda: not window.isVisible(), timeout=2000)
        assert page.draft is None
        assert page.pending is None
        assert not page.unsaved
        if action == "logout":
            assert page.workspace is None and not page.body.toPlainText()
    finally:
        release.set()
        qtbot.waitUntil(lambda: not page.running, timeout=10000)


def test_normal_delayed_delivery_updates_gui_thread(email_window, qtbot, monkeypatch):
    page = email_window.scenario_page.email_page
    states = []
    page.state_changed.connect(lambda state: states.append((state, get_ident())))
    open_generated(email_window, qtbot)
    assert all(thread == get_ident() for _, thread in states)
    assert states[-1][0] == MaterialState.UNSAVED


def test_unconfigured_startup_selection_do_not_generate(
    email_window, qtbot, scenario_env
):
    window = MainWindow(scenario_env.accounts)
    qtbot.addWidget(window)
    window.show()
    window._authenticated(scenario_env.tokens["teacher"])
    window.navigate(View.CONSTRUCTOR)
    window.scenario_list.setCurrentRow(0)
    window._sync_session()
    mock = window.emails.gateway._providers[Provider.MOCK]
    assert mock.calls == 0
    window.scenario_page.open_email()
    page = window.scenario_page.email_page
    assert not page.generate_button.isEnabled() and not page.save_button.isEnabled()
    assert "не налаштовано" in page.provider.text()
    assert mock.calls == 0


def test_long_unicode_wrap_and_layout_at_supported_sizes(
    email_window, qtbot, monkeypatch
):
    from cyberforge.application import email_demo

    original = email_demo.demo_gateway

    def long_mail(source):
        gateway = original(source)
        mock = gateway._providers[Provider.MOCK]
        payload = json.loads(mock._responses[0].text)
        payload["main"]["body_text"] = (
            "Навчальний український текст із літерами ї є ґ.\n" * 70
        )
        payload["main"]["subject"] = "У" * 4000
        payload["main"]["sender_address"] = "sender@" + "d" * 200 + ".invalid"
        payload["background"] *= 4
        mock._responses.clear()
        mock._responses.append(ProviderResponse(text=json.dumps(payload)))
        return gateway

    monkeypatch.setattr(email_demo, "demo_gateway", long_mail)
    page = open_generated(email_window, qtbot)
    assert page.messages.count() == 9
    page.preview.open_message(0)
    assert "ї є ґ" in page.body.toPlainText()
    assert page.body.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
    for width, height in [(1100, 720), (1400, 900), (1920, 1080)]:
        email_window.resize(width, height)
        qtbot.wait(30)
        scroll = email_window.containers[View.CONSTRUCTOR]
        assert scroll.horizontalScrollBar().maximum() == 0
        assert page.body.horizontalScrollBar().maximum() == 0
        assert page.body.verticalScrollBar().maximum() > 0
        assert page.subject.horizontalScrollBar().maximum() == 0
        assert page.subject.verticalScrollBar().maximum() > 0
        assert page.sender.horizontalScrollBar().maximum() == 0
        ratio = page.preview.width() / (page.width() - 32)
        assert 0.8 <= ratio <= 0.96


def test_external_save_and_parameter_change_do_not_erase_candidate(email_window, qtbot):
    window = email_window
    page = open_generated(window, qtbot)
    draft, workspace = page.draft, page.workspace
    window.emails.save(window._token, workspace, draft)
    window._sync_session()
    assert page.stale and page.unsaved and page.draft == draft
    assert page.status.text() == MaterialState.REVIEW
    assert not page.save_button.isEnabled()


def test_readonly_foreign_admin_and_archived_constructor(
    email_window, qtbot, scenario_env
):
    window = email_window
    page = open_generated(window, qtbot)
    assert page.save()
    scenario = window.scenario_page.scenario
    window.scenarios.archive(
        window._token,
        scenario.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=0,
    )
    window._signed_out()
    window._authenticated(scenario_env.tokens["admin"])
    window.navigate(View.CONSTRUCTOR)
    window.archive_filter.setChecked(True)
    window.scenario_list.setCurrentRow(0)
    window.scenario_page.open_email()
    assert page.draft is not None
    assert page.refinement.isReadOnly()
    assert not page.generate_button.isEnabled() and not page.save_button.isEnabled()
    assert page.code_button.isEnabled()


def test_database_failure_does_not_fake_green_border(email_window, qtbot):
    window = email_window
    page = open_generated(window, qtbot)
    with window.accounts.database.engine.begin() as db:
        db.execute(
            text(
                "CREATE TRIGGER fail_email_insert BEFORE INSERT ON email_materials "
                "BEGIN SELECT RAISE(ABORT, 'secret database detail'); END"
            )
        )
    draft = page.draft
    assert not page.save()
    assert page.draft == draft and page.unsaved
    assert not window.scenario_page.email_material.property("saved")
    assert "secret" not in page.message.text()
