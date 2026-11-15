"""Web workspace and real browser/editor integration with an isolated offline DB."""

import json
from threading import Event, get_ident

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from cyberforge.application.email_materials import EmailMaterialService, MaterialState
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.factory import create_gateway
from cyberforge.ui.navigation import View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme
from cyberforge.ui.web_editor import WebEditorDialog
from cyberforge.ui.web_source import WebSourceDialog


@pytest.fixture
def web_window(qtbot, qapp, scenario_env):
    env = scenario_env
    apply_theme(qapp)
    emails = EmailMaterialService(env.service, create_gateway(), demo=True)
    webs = WebMaterialService(emails, demo=True)
    window = MainWindow(env.accounts, emails, webs)
    qtbot.addWidget(
        window, before_close_func=lambda widget: widget.scenario_page.clear()
    )
    window._authenticated(env.tokens["teacher"])
    window.navigate(View.CONSTRUCTOR)
    scenario = env.service.create(
        env.tokens["teacher"],
        dict(topic="Навчальний доступ до матеріалів", difficulty="beginner"),
    )
    workspace = emails.load(env.tokens["teacher"], scenario)
    emails.save(
        env.tokens["teacher"],
        workspace,
        emails.generate(env.tokens["teacher"], workspace),
    )
    window.scenario_page.load(scenario, editable=True)
    window.resize(1100, 720)
    window.show()
    yield window
    qtbot.waitUntil(lambda: not window.scenario_page.web_page.running, timeout=10000)


def generate(window, qtbot):
    window.scenario_page.open_web()
    page = window.scenario_page.web_page
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft is not None, page.message.text()
    return page


def test_open_select_generate_explicit_save_reopen(web_window, qtbot):
    window = web_window
    window.scenario_page.open_web()
    page = window.scenario_page.web_page
    assert page.preset.currentData() == "auto"
    assert page.draft is None
    page.preset.setCurrentIndex(page.preset.findData("login"))
    page.theme.setCurrentIndex(page.theme.findData("service"))
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft.preset == "login" and page.draft.page.theme == "service"
    browser = page.browser
    assert browser.address.isReadOnly()
    assert browser.address.text() == page.draft.page.display_url
    assert not browser.back.isEnabled() and not browser.forward.isEnabled()
    with qtbot.waitSignal(browser.page.loadFinished, timeout=10000):
        browser.reload.click()
    assert page.unsaved
    assert window.scenario_page.web_status.text() == MaterialState.UNSAVED
    assert page.service.load(window._token, page.workspace.scenario).draft is None
    draft = page.draft
    assert page.save()
    assert window.scenario_page.web_material.property("saved")
    window.scenario_page.open_web()
    assert page.draft == draft and not page.unsaved
    page.preset.setCurrentIndex(page.preset.findData("portal"))
    assert page.draft == draft
    assert page.service.load(window._token, page.workspace.scenario).draft == draft


def test_editor_add_remove_reorder_apply_cancel_and_sources(web_window, qtbot):
    page = generate(web_window, qtbot)
    saved = page.service.save(web_window._token, page.workspace, page.draft)
    page.workspace, page.unsaved = saved, False
    original = page.draft

    def edit():
        dialog = next(d for d in page.findChildren(WebEditorDialog) if d.isVisible())
        dialog.components.setCurrentRow(1)
        dialog.fields["text"].setPlainText("Ручна правка для навчання")
        dialog.kind.setCurrentIndex(dialog.kind.findData("text"))
        dialog.add_button.click()
        assert len(dialog.data["components"]) == len(original.page.components) + 1
        current = dialog.selected
        dialog.up_button.click()
        assert dialog.selected == current - 1
        dialog.down_button.click()
        dialog.remove_button.click()
        assert len(dialog.data["components"]) == len(original.page.components)
        dialog.theme.setCurrentIndex(dialog.theme.findData("corporate"))
        dialog.apply()

    QTimer.singleShot(0, edit)
    page.edit_button.click()
    assert (
        page.unsaved
        and page.draft.page.components[1].text == "Ручна правка для навчання"
    )
    assert page.draft.page.theme == "corporate"
    assert (
        page.service.load(web_window._token, page.workspace.scenario).draft == original
    )
    working = page.draft

    def cancel():
        dialog = next(d for d in page.findChildren(WebEditorDialog) if d.isVisible())
        dialog.title.setText("Не застосовувати")
        dialog.reject()

    QTimer.singleShot(0, cancel)
    page.edit_button.click()
    assert page.draft == working

    def inspect():
        dialog = next(d for d in page.findChildren(WebSourceDialog) if d.isVisible())
        assert dialog.sources["HTML"].toPlainText() == page.browser.rendered.html
        assert dialog.sources["CSS"].toPlainText() == page.browser.rendered.css
        assert json.loads(dialog.sources["JSON"].toPlainText()) == working.model_dump(
            mode="json"
        )
        for i in range(3):
            dialog.tabs.setCurrentIndex(i)
            assert dialog.tabs.currentWidget().isReadOnly()
            dialog.copy_button.click()
            assert (
                QApplication.clipboard().text()
                == dialog.tabs.currentWidget().toPlainText()
            )
        dialog.accept()

    QTimer.singleShot(0, inspect)
    page.code_button.click()
    assert page.save()


def test_invalid_editor_does_not_apply(web_window, qtbot):
    page = generate(web_window, qtbot)
    old = page.draft

    def invalid():
        dialog = next(d for d in page.findChildren(WebEditorDialog) if d.isVisible())
        dialog.components.setCurrentRow(1)
        dialog.fields["text"].setPlainText("<script>alert(1)</script>")
        dialog.apply()
        assert dialog.isVisible() and dialog.error.text()
        dialog.reject()

    QTimer.singleShot(0, invalid)
    page.edit_button.click()
    assert page.draft == old


def test_unsaved_guards_and_failure_preserve_material(web_window, qtbot, monkeypatch):
    page = generate(web_window, qtbot)
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    assert not page.can_leave()
    original = page.draft

    def failed(*args, **kwargs):
        assert kwargs["previous"] == original
        raise ApplicationError("Тимчасова помилка")

    monkeypatch.setattr(page.service, "generate", failed)
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft == original and page.unsaved
    assert page.message.text() == "Тимчасова помилка"
    monkeypatch.setattr(page, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    assert page.can_leave() and not page.unsaved and page.draft is None


def test_worker_result_cannot_cross_session_or_scenario(web_window, qtbot, monkeypatch):
    page = generate(web_window, qtbot)
    page.unsaved = False
    original = page.draft
    entered, release = Event(), Event()
    main_thread = get_ident()

    def delayed(*args, **kwargs):
        assert get_ident() != main_thread
        entered.set()
        assert release.wait(5)
        return original

    monkeypatch.setattr(page.service, "generate", delayed)
    page.generate_button.click()
    qtbot.waitUntil(entered.is_set, timeout=3000)
    assert page.progress.isVisible()
    page.clear()
    release.set()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft is None and page.workspace is None


def test_current_manual_draft_in_protected_refinement(web_window, qtbot):
    page = generate(web_window, qtbot)
    original = page.draft
    data = original.page.model_dump(mode="json")
    data["components"][1]["title"] = "Ручний заголовок"
    from cyberforge.web.contracts import WebPageV2

    manual = page.service.edit(
        web_window._token,
        page.workspace,
        original,
        WebPageV2.model_validate_json(json.dumps(data)),
    )
    page.draft = manual
    page.scope.setCurrentIndex(page.scope.findData("text"))
    page.refinement.setPlainText("Скороти текст")
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft.page.components[1].title == "Ручний заголовок"
    assert page.draft.source_digest == manual.source_digest
    assert page.unsaved


def layout_metrics(page, viewport):
    from PySide6.QtWidgets import QWidget

    controls = {}
    for name in (
        "preset",
        "theme",
        "scope",
        "selected_component",
        "provider",
        "status",
        "title",
        "refinement",
        "code_button",
        "edit_button",
        "generate_button",
        "save_button",
        "browser",
    ):
        control = getattr(page, name)
        controls[name] = (
            control.width(),
            control.minimumWidth(),
            control.minimumSizeHint().width(),
            control.sizeHint().width(),
        )
    controls["browser_children"] = [
        (
            type(c).__name__,
            c.width(),
            c.minimumWidth(),
            c.minimumSizeHint().width(),
            c.sizeHint().width(),
        )
        for c in page.browser.findChildren(QWidget)
        if c.isVisible() and c.minimumSizeHint().width() > 200
    ]
    data = {
        "viewport": viewport.width(),
        "page": (
            page.width(),
            page.minimumWidth(),
            page.minimumSizeHint().width(),
            page.sizeHint().width(),
        ),
        "controls": controls,
        "rows": [
            (
                page.layout().itemAt(i).minimumSize().width(),
                page.layout().itemAt(i).sizeHint().width(),
            )
            for i in range(page.layout().count())
        ],
    }
    print("WEB_LAYOUT_METRICS " + json.dumps(data))
    return data


def test_compact_critical_controls_and_browser_width(web_window, qtbot):
    page = generate(web_window, qtbot)
    qtbot.wait(100)
    viewport = web_window.containers[View.CONSTRUCTOR].viewport()
    assert page.width() <= viewport.width(), layout_metrics(page, viewport)
    assert page.minimumSizeHint().width() <= viewport.width(), layout_metrics(
        page, viewport
    )
    assert 0.8 <= page.browser.width() / page.width() <= 0.95
    assert page.browser.view.height() >= 150
    assert page.save_button.isVisible() and page.edit_button.isVisible()
    assert web_window.width() == 1100
    assert web_window.scenario_page.web_status.text() == MaterialState.UNSAVED


def test_compact_native_combo_metrics_cannot_widen_workspace(web_window, qtbot):
    page = generate(web_window, qtbot)
    # Larger native glyph metrics reproduce the Windows minimum-hint pressure
    # on Linux too, without relaxing the actual viewport/overflow assertions.
    for control in (page.preset, page.theme, page.scope, page.selected_component):
        control.setStyleSheet("font-size:20px")
    qtbot.wait(100)
    viewport = web_window.containers[View.CONSTRUCTOR].viewport()
    assert page.width() <= viewport.width(), layout_metrics(page, viewport)
    assert page.minimumSizeHint().width() <= viewport.width(), layout_metrics(
        page, viewport
    )
    assert web_window.containers[View.CONSTRUCTOR].horizontalScrollBar().maximum() == 0


def test_stale_saved_email_blocks_edit_and_can_regenerate(web_window, qtbot):
    page = generate(web_window, qtbot)
    assert page.save()
    web_window.scenario_page.open_web()
    old = page.draft
    email_workspace = page.service.emails.load(
        web_window._token, page.workspace.scenario
    )
    page.service.emails.save(web_window._token, email_workspace, email_workspace.draft)
    page.observe(page.workspace.scenario)
    assert page.stale and not page.save_button.isEnabled()
    scenario = page.workspace.scenario
    page.clear()
    page.open(scenario, editable=True)
    assert page.draft == old and page.workspace.state == MaterialState.REVIEW
    assert not page.edit_button.isEnabled()
    page.generate_button.click()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft.email_binding != old.email_binding
    assert page.save_button.isEnabled()


def test_actual_signout_switch_ignores_delayed_web_result(
    web_window, qtbot, monkeypatch, scenario_env
):
    page = generate(web_window, qtbot)
    page.unsaved = False
    original = page.draft
    entered, release = Event(), Event()

    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original

    monkeypatch.setattr(page.service, "generate", delayed)
    page.generate_button.click()
    qtbot.waitUntil(entered.is_set, timeout=3000)
    web_window._signed_out()
    web_window._authenticated(scenario_env.tokens["other"])
    web_window.navigate(View.CONSTRUCTOR)
    release.set()
    qtbot.waitUntil(lambda: not page.running, timeout=10000)
    assert page.draft is None and page.workspace is None
    assert page.browser.draft is None
    assert not web_window.scenario_page.active


def test_closing_waits_asynchronously_for_web_worker(web_window, qtbot, monkeypatch):
    page = generate(web_window, qtbot)
    page.unsaved = False
    old = page.draft
    entered, release = Event(), Event()

    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return old

    monkeypatch.setattr(page.service, "generate", delayed)
    page.generate_button.click()
    qtbot.waitUntil(entered.is_set, timeout=3000)
    assert not web_window.close()
    assert web_window._closing_pending and web_window.isVisible()
    QTimer.singleShot(100, release.set)
    qtbot.waitUntil(lambda: not web_window.isVisible(), timeout=5000)
    assert not page.running
    # MainWindow has already disposed its browser. The fixture's second cleanup
    # only clears draft controls before deleting the closed top-level widget.
    page.browser = None


def test_long_valid_tab_title_does_not_expand_compact_browser(web_window, qtbot):
    from cyberforge.web.contracts import WebDraftV3

    page = generate(web_window, qtbot)
    data = page.draft.model_dump(mode="json")
    data["page"]["tab_title"] = "Н" * 150
    data["page"]["display_url"] = "https://portal.example/" + "a" * 470
    page.draft = WebDraftV3.model_validate_json(json.dumps(data))
    page._render()
    qtbot.wait(100)
    viewport = web_window.containers[View.CONSTRUCTOR].viewport()
    assert page.width() <= viewport.width(), layout_metrics(page, viewport)
    assert page.browser.tab.toolTip() == page.draft.page.tab_title
    assert page.browser.address.text() == page.draft.page.display_url
