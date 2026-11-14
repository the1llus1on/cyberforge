"""Real Email agent/gateway in a responsive native Qt workspace, without network."""

import json
import socket
from threading import Event, get_ident

import pytest
from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QPalette, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QToolButton,
)
from sqlalchemy import text

from cyberforge.agents.contracts import MessageV1
from cyberforge.application.email_materials import EmailMaterialService, MaterialState
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    Provider,
    ProviderResponse,
)
from cyberforge.llm.factory import create_gateway
from cyberforge.ui.email_body import MessageBody
from cyberforge.ui.email_source import EmailSourceDialog
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


def layout_metrics(page, scroll):
    return {
        "viewport": scroll.viewport().size().toTuple(),
        "page": page.size().toTuple(),
        "minimum_hints": {
            name: field.minimumSizeHint().toTuple()
            for name, field in (
                ("preview", page.preview),
                ("reading", page.preview.reading),
                ("body", page.body),
                ("subject", page.subject),
                ("sender", page.sender),
                ("recipient", page.preview.recipient),
                ("timestamp", page.timestamp),
            )
        },
    }


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
    assert page.draft.slots.main.body_text in page.body.toPlainText()
    assert page.draft.slots.main.sender_name in page.body.toPlainText()
    assert page.draft.slots.internal_resource_id in page.body.toPlainText()
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
            assert "JSON" in dialog.explanation.text()
            assert dialog.findChild(QTextEdit) is None
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
    scroll = window.containers[View.CONSTRUCTOR]
    viewport = scroll.viewport()
    for control in (card.save_button, card.revert_button):
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().topLeft())
        ), layout_metrics(page, scroll)
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().bottomRight())
        ), layout_metrics(page, scroll)
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
    assert original.slots.main.body_text in page.body.toPlainText()
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
@pytest.mark.parametrize("header_reserve", [0, 8])
def test_compact_mailbox_keeps_critical_controls_visible(
    email_window, qtbot, opened, header_reserve
):
    window = email_window
    window.resize(1100, 720)
    # Reserve room for differing native toolbar/font metrics at the same size.
    window.topbar.setMinimumHeight(window.topbar.height() + header_reserve)
    page = open_generated(window, qtbot)
    if opened:
        page.preview.open_message(0)
    qtbot.wait(20)
    scroll = window.containers[View.CONSTRUCTOR]
    viewport = scroll.viewport()
    for control in (
        page.back_button,
        page.edit_button,
        page.refinement_scope,
        page.refinement,
        page.code_button,
        page.generate_button,
        page.save_button,
    ):
        assert control.isVisible()
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().topLeft())
        ), layout_metrics(page, scroll)
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().bottomRight())
        ), layout_metrics(page, scroll)
    assert scroll.horizontalScrollBar().maximum() == 0, layout_metrics(page, scroll)
    assert scroll.verticalScrollBar().maximum() == 0, layout_metrics(page, scroll)
    if opened:
        assert page.body.height() >= page.body.minimumHeight()
        assert (
            page.body.viewport().height() >= page.body.fontMetrics().lineSpacing() * 3
        )
    assert page.preview.folders.width() < 60


def test_reading_hierarchy_vector_icons_and_inert_resource(email_window, qtbot):
    page = open_generated(email_window, qtbot)
    preview = page.preview
    preview.open_message(0)
    assert 20 <= preview.subject.font().pixelSize() <= 22
    assert 14 <= preview.body.font().pixelSize() <= 15
    assert preview.sender.mapTo(preview, preview.sender.rect().topLeft()).x() == (
        preview.recipient.mapTo(preview, preview.recipient.rect().topLeft()).x()
    )
    for control in preview.findChildren(QToolButton):
        assert not control.icon().isNull() and not control.text()
        # Qt owns the line edit's clear/search buttons and their accessibility.
        if control.parentWidget() is not preview.search:
            assert control.accessibleName()
    assert not preview.reply.icon().isNull()
    assert not preview.forward.icon().isNull() and not preview.forward.isEnabled()
    assert "перехід вимкнено" in preview.body.toPlainText()
    assert page.draft.slots.internal_resource_id in preview.body.toPlainText()
    assert page.draft.slots.main.body_text in preview.body.toPlainText()
    body_start = preview.body.document().find(page.draft.slots.main.body_text[:7])
    assert 14 <= body_start.charFormat().font().pixelSize() <= 15
    assert 120 <= body_start.blockFormat().lineHeight() <= 150


def test_native_text_size_hints_cannot_widen_compact_reading_view(
    request, monkeypatch, qtbot
):
    from cyberforge.ui import email_preview

    class WideNativeBody(MessageBody):
        def minimumSizeHint(self):
            return QSize(1200, 65)

    class TallNativeInbox(QListWidget):
        def sizeHint(self):
            return QSize(256, 1800)

    monkeypatch.setattr(email_preview, "MessageBody", WideNativeBody)
    monkeypatch.setattr(email_preview, "QListWidget", TallNativeInbox)
    window = request.getfixturevalue("email_window")
    window.resize(1100, 720)
    page = open_generated(window, qtbot)
    page.preview.open_message(0)
    qtbot.wait(30)
    scroll = window.containers[View.CONSTRUCTOR]
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() == 0
    for control in (page.refinement, page.save_button):
        assert (
            scroll.viewport()
            .rect()
            .contains(control.mapTo(scroll.viewport(), control.rect().bottomRight()))
        )


def test_wrapped_label_preferred_heights_cannot_expand_email_page(
    request, monkeypatch, qtbot
):
    from cyberforge.ui import email_page

    class TallPreferredLabel(QLabel):
        def sizeHint(self):
            hint = super().sizeHint()
            return QSize(hint.width(), max(200, hint.height()))

    def native_label(text, kind="muted"):
        control = TallPreferredLabel(text)
        control.setProperty("kind", kind)
        control.setWordWrap(True)
        control.setTextFormat(Qt.TextFormat.PlainText)
        control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return control

    monkeypatch.setattr(email_page, "label", native_label)
    window = request.getfixturevalue("email_window")
    window.resize(1100, 720)
    page = open_generated(window, qtbot)
    page.preview.open_message(0)
    qtbot.wait(30)
    scroll = window.containers[View.CONSTRUCTOR]
    assert scroll.verticalScrollBar().maximum() == 0, layout_metrics(page, scroll)
    for field in (page.provider, page.message, page.refinement_help):
        assert field.height() >= field.heightForWidth(field.width())
    for control in (page.refinement, page.save_button):
        assert (
            scroll.viewport()
            .rect()
            .contains(control.mapTo(scroll.viewport(), control.rect().bottomRight()))
        ), layout_metrics(page, scroll)


def test_native_message_template_keeps_injection_as_literal_text(qtbot):
    field = MessageBody()
    qtbot.addWidget(field)
    message = MessageV1.model_construct(
        sender_name='<img src="file:///private.png">',
        sender_address="sender@training.invalid",
        subject="Синтетична перевірка",
        body_text='<script>alert(1)</script>\n\n<a href="https://example.invalid">текст</a>',
    )
    before = message.model_dump_json()
    field.set_message(message, "scenario_1_v1")
    field.show()
    rendered = field.toPlainText()
    assert message.sender_name in rendered and message.body_text in rendered
    assert "scenario_1_v1" in rendered
    assert message.model_dump_json() == before
    assert field.isReadOnly() and not field.acceptRichText()
    qtbot.keyClicks(field, "cannot-edit")
    assert field.toPlainText() == rendered
    for style in field.document().allFormats():
        assert not style.isImageFormat()
        if style.isCharFormat():
            assert not style.toCharFormat().isAnchor()
    for address in ("file:///private.png", "https://example.invalid/image.png"):
        assert (
            field.document().resource(
                QTextDocument.ResourceType.ImageResource, QUrl(address)
            )
            is None
        )


def test_formatted_background_preserves_paragraphs_without_main_card(qtbot):
    field = MessageBody()
    qtbot.addWidget(field)
    message = MessageV1(
        sender_name="Навчальна бібліотека",
        sender_address="library@training.invalid",
        subject="Матеріали",
        body_text="Перший абзац — ї є ґ.\n\nДругий абзац.\n",
    )
    field.set_message(message, None)
    assert field.toPlainText() == message.body_text
    assert "Навчальний ресурс" not in field.toPlainText()


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
    assert page.body.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth
    for width, height in [(1100, 720), (1400, 900), (1920, 1080)]:
        email_window.resize(width, height)
        qtbot.wait(30)
        scroll = email_window.containers[View.CONSTRUCTOR]
        assert scroll.horizontalScrollBar().maximum() == 0, layout_metrics(page, scroll)
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


def test_visual_editor_apply_cancel_json_save_reopen(email_window, qtbot):
    from cyberforge.ui.email_editor import EmailEditorDialog

    page = open_generated(email_window, qtbot)
    assert page.save()
    email_window.scenario_page.open_email()
    original = page.draft
    page.preview.open_message(0)

    def edit_main():
        dialog = page.findChild(EmailEditorDialog)
        dialog.fields["sender_name"].setText("Навчальний редактор")
        dialog.fields["sender_address"].setText("maxim@ukr.net")
        dialog.fields["subject"].setText("Локальна тема")
        dialog.body.setPlainText("Змінений текст для навчання.")
        dialog.apply()

    QTimer.singleShot(0, edit_main)
    page.edit_button.click()
    assert page.unsaved and page.manual_edits
    assert page.draft.slots.main.sender_address == "maxim@ukr.net"
    assert page.subject.toPlainText() == "Локальна тема"
    assert page.draft.slots.main.body_text in page.body.toPlainText()
    assert page.draft.artifact.context.sender_name == "Навчальний редактор"
    assert (
        email_window.emails.load(email_window._token, page.workspace.scenario).draft
        == original
    )
    edited = page.draft

    def cancel():
        dialog = [d for d in page.findChildren(EmailEditorDialog) if d.isVisible()][0]
        dialog.fields["subject"].setText("Не застосовувати")
        dialog.reject()

    QTimer.singleShot(0, cancel)
    page.edit_button.click()
    assert page.draft == edited

    def inspect_json():
        dialog = page.findChild(EmailSourceDialog)
        assert json.loads(dialog.source.toPlainText()) == edited.model_dump(mode="json")
        assert dialog.source.isReadOnly()
        dialog.copy_button.click()
        assert QApplication.clipboard().text() == dialog.source.toPlainText()
        dialog.accept()

    QTimer.singleShot(0, inspect_json)
    page.code_button.click()
    assert page.save()
    email_window.scenario_page.open_email()
    assert page.draft == edited and not page.unsaved
    page.preview.open_message(1)

    def edit_background():
        dialog = [d for d in page.findChildren(EmailEditorDialog) if d.isVisible()][0]
        dialog.fields["subject"].setText("Фоновий лист після відкриття")
        dialog.apply()

    QTimer.singleShot(0, edit_background)
    page.edit_button.click()
    assert page.draft.slots.background[0].subject == "Фоновий лист після відкриття"
    assert page.draft.slots.main == edited.slots.main


def test_visual_editor_invalid_and_refinement_retains_manual(
    email_window, qtbot, monkeypatch
):
    from cyberforge.ui.email_editor import EmailEditorDialog

    page = open_generated(email_window, qtbot)
    original = page.draft

    def invalid():
        dialog = [d for d in page.findChildren(EmailEditorDialog) if d.isVisible()][0]
        dialog.fields["sender_address"].setText("bad@@example.com")
        dialog.apply()
        assert dialog.isVisible() and dialog.error.text()
        dialog.reject()

    QTimer.singleShot(0, invalid)
    page.edit_button.click()
    assert page.draft == original
    manual = email_window.emails.edit(
        email_window._token,
        page.workspace,
        original,
        index=0,
        message=original.slots.main.model_copy(update={"subject": "Ручна тема"}),
    )
    page.draft, page.unsaved, page.manual_edits = manual, True, True
    page._render_draft()
    page.refinement.setPlainText("Скороти лише текст основного листа")
    monkeypatch.setattr(page, "confirm_regeneration", lambda: False)
    page.generate_button.click()
    assert page.draft == manual and not page.running
    monkeypatch.setattr(page, "confirm_regeneration", lambda: True)
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft.slots.main.subject == "Ручна тема"
    assert page.draft.slots.background == manual.slots.background
    assert page.unsaved


def test_failed_ai_after_manual_apply_keeps_working_and_saved(
    email_window, qtbot, monkeypatch
):
    page = open_generated(email_window, qtbot)
    assert page.save()
    email_window.scenario_page.open_email()
    saved = page.draft
    manual = email_window.emails.edit(
        email_window._token,
        page.workspace,
        saved,
        index=0,
        message=saved.slots.main.model_copy(
            update={"subject": "Ручна тема перед помилкою"}
        ),
    )
    page.draft, page.unsaved, page.manual_edits = manual, True, True
    page._render_draft()
    monkeypatch.setattr(page, "confirm_regeneration", lambda: True)
    received = []

    def fail(token, workspace, **kwargs):
        received.append(kwargs["previous"])
        raise ApplicationError("Тимчасова помилка генерації")

    monkeypatch.setattr(email_window.emails, "generate", fail)
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert received == [manual]
    assert page.draft == manual and page.unsaved and page.manual_edits
    assert (
        email_window.emails.load(email_window._token, page.workspace.scenario).draft
        == saved
    )


def test_editor_does_not_truncate_existing_legacy_fields(qtbot):
    from cyberforge.ui.email_editor import EmailEditorDialog

    message = MessageV1(
        sender_name="С" * 250,
        sender_address="sender@training.invalid",
        subject="Т" * 4000,
        body_text="Текст",
    )
    received = []
    dialog = EmailEditorDialog(message, received.append)
    qtbot.addWidget(dialog)
    assert dialog.fields["subject"].text() == message.subject
    assert dialog.fields["sender_name"].text() == message.sender_name
    dialog.reject()
    assert not received


def test_manual_regeneration_confirmation_defaults_to_keep(email_window):
    page = email_window.scenario_page.email_page

    def keep():
        box = page.findChild(QMessageBox)
        assert box.defaultButton().text() == "Залишити чернетку"
        assert box.button(QMessageBox.StandardButton.Yes).text() == "Перегенерувати"
        box.defaultButton().click()

    QTimer.singleShot(0, keep)
    assert not page.confirm_regeneration()
