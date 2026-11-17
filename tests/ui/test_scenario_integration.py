"""Instructor publication UX with isolated synthetic offline materials."""

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.groups.service import GroupService
from cyberforge.llm.factory import create_gateway
from cyberforge.ui.navigation import View
from cyberforge.ui.scenario_integration import IntegrationDialog
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import STYLE, apply_theme


@pytest.fixture
def integration_window(qtbot, qapp, scenario_env):
    env = scenario_env
    if qapp.styleSheet() != STYLE:
        apply_theme(qapp)
    token = env.tokens["teacher"]
    emails = EmailMaterialService(env.service, create_gateway(), demo=True)
    webs = WebMaterialService(emails, demo=True)
    env.scenario = env.service.create(
        token, dict(topic="Навчальний сценарій", difficulty="beginner")
    )
    ew = emails.load(token, env.scenario)
    emails.save(token, ew, emails.generate(token, ew))
    ww = webs.load(token, env.scenario)
    webs.save(token, ww, webs.generate(token, ww))
    env.group = GroupService(env.accounts).save_group(
        env.tokens["admin"],
        "Група UI",
        instructors=(env.accounts.current(token).id,),
        learners=(),
    )
    window = MainWindow(env.accounts, emails, webs)
    qtbot.addWidget(window, before_close_func=lambda w: w.scenario_page.clear())
    window._authenticated(token)
    window.navigate(View.CONSTRUCTOR)
    window.scenario_page.load(env.scenario, editable=True)
    window.resize(1100, 720)
    window.show()
    window.test_env = env
    return window


def dialog(window, qtbot):
    page = window.scenario_page
    widget = IntegrationDialog(
        page.integration, lambda: window._token, page.scenario, owned=True, parent=page
    )
    qtbot.addWidget(widget, before_close_func=lambda d: d.force_close())
    widget.show()
    return widget


def configure(widget):
    assert widget.save_link()
    widget.criteria["email.sender"][0].setChecked(True)
    widget.criteria["transition.safe_decline"][0].setChecked(True)
    widget.criteria["web.address"][0].setChecked(True)
    assert widget.save_rubric()
    widget.groups.item(0).setCheckState(Qt.CheckState.Checked)
    assert widget.report.technical_ready


def test_editors_readiness_inert_preview_and_cancel(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    assert not d.report.technical_ready
    assert not d.save_rubric()
    assert "Рубрика" in d.message.text()
    configure(d)
    assert d.state.link.display_url in d.mail.body.toPlainText()
    assert d.state.link.link_label in d.mail.body.toPlainText()
    assert "href=" not in d.mail.body.toHtml()
    d.mail.open_message(1)
    assert d.state.link.display_url not in d.mail.body.toPlainText()
    d.mail.open_message(0)
    assert d.state.link.display_url in d.mail.body.toPlainText()
    assert not d.publish()
    assert "підтвердьте" in d.message.text()
    d.ack.setChecked(True)
    monkeypatch.setattr(d, "final_confirmation", lambda: False)
    assert d.publish() is False
    assert window.scenario_page.publications.history(window._token, d.expected.id) == ()
    assert d.ack.isChecked()
    d.groups.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not d.ack.isChecked()
    d.link_label.setText("Незбережена назва")
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    d.reject()
    assert d.isVisible() and d.dirty
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    d.reject()
    assert not d.isVisible()
    state = window.scenario_page.integration.inspect(
        window._token, window.test_env.scenario
    )
    assert state.link.link_label != "Незбережена назва"


def test_explicit_publication_readonly_grants_and_next_draft(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    configure(d)
    d.ack.setChecked(True)
    monkeypatch.setattr(d, "final_confirmation", lambda: True)
    assert d.publish(), d.message.text()
    assert d.expected.status == "published"
    assert not d.save_link_button.isEnabled()
    assert not d.save_rubric_button.isEnabled()
    assert d.link_label.isReadOnly() and d.display_url.isReadOnly()
    assert not d.publish_button.isEnabled()
    assert d.grant_groups.count() == 1
    d.grant_groups.setCurrentRow(0)
    monkeypatch.setattr(d, "confirm_grant", lambda publication, group_id, active: True)
    d.change_grant(False)
    assert "revoke" in d.audit_text.toPlainText()
    d.change_grant(True)
    assert len(d.publications.audit(window._token, d.history.currentData())) == 3
    d.reject()
    page = window.scenario_page
    page.load(
        window.scenarios.get(window._token, window.test_env.scenario.id), editable=True
    )
    assert page.new_version_button.isVisible()
    assert "Опубліковано" in page.integration_status.text()
    page.create_next_version()
    assert page.scenario.version == 2 and page.scenario.status == "draft"
    assert not page.new_version_button.isVisible()
    assert page.emails.load(window._token, page.scenario).draft is None
    assert len(page.publications.history(window._token, page.scenario.id)) == 1
    historical = dialog(window, qtbot)
    assert historical.history.currentData() is None  # New draft has no grant target.
    historical.history.setCurrentIndex(0)
    historical.load_history()
    assert historical.expected.version == 1 and not historical.writable
    assert historical.mail.draft is not None


def test_unsaved_save_remain_guard_and_source_changed_after_review(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    configure(d)
    d.link_label.setText("Явно збережена назва")
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Save)
    d.reject()
    assert not d.isVisible()
    assert (
        window.scenario_page.integration.inspect(
            window._token, window.test_env.scenario
        ).link.link_label
        == "Явно збережена назва"
    )
    d = dialog(window, qtbot)
    d.groups.item(0).setCheckState(Qt.CheckState.Checked)
    d.ack.setChecked(True)
    ew = window.emails.load(window._token, d.expected)
    window.emails.save(window._token, ew, ew.draft)
    monkeypatch.setattr(d, "final_confirmation", lambda: True)
    assert not d.publish()
    assert d.publications.history(window._token, d.expected.id) == ()
    d.check_readiness()
    assert d.report is None and not d.publish_button.isEnabled()


def test_session_change_clears_open_review_and_forbids_old_actions(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    d = dialog(window, qtbot)
    configure(d)
    d.ack.setChecked(True)
    window._authenticated(window.test_env.tokens["other"])
    assert not d.publish()
    assert "Сесію змінено" in d.message.text()
    window.scenario_page.clear()
    assert not d.isVisible() and d.state is None and d.mail.draft is None
    assert d.link_label.text() == d.display_url.text() == ""


def test_compact_page_and_scrollable_dialog(integration_window, qtbot):
    window = integration_window
    page = window.scenario_page
    qtbot.wait(30)
    viewport = window.containers[View.CONSTRUCTOR].viewport()
    for control in (page.save_button, page.integration_button):
        assert viewport.rect().contains(
            control.mapTo(viewport, control.rect().bottomRight())
        )
    assert page.width() <= viewport.width()
    d = dialog(window, qtbot)
    configure(d)
    assert d.width() <= 1100 and d.height() <= 720
    for index in range(3):
        assert d.navigate(index)
        qtbot.wait(10)
        scroll = d.steps[index]
        assert scroll.widget().width() <= scroll.viewport().width()
        action = (d.save_link_button, d.save_rubric_button, d.publish_button)[index]
        assert action.isVisible()
        assert d.rect().contains(action.mapTo(d, action.rect().bottomRight()))
    assert d.rect().contains(
        d.close_buttons.mapTo(d, d.close_buttons.rect().bottomRight())
    )


def test_published_weight_precision_and_explicit_invalid_weight(
    integration_window, qtbot
):
    d = dialog(integration_window, qtbot)
    d.criteria["email.sender"][0].setChecked(True)
    d.criteria["email.sender"][1].setText("0.000000000123")
    assert d.save_rubric()
    assert d.state.rubric.criteria[0].weight == 0.000000000123
    d.criteria["email.sender"][1].setText("nan")
    assert not d.save_rubric()
    assert "Вага" in d.message.text()


def test_actual_web_review_and_repeated_close(integration_window, qtbot):
    d = dialog(integration_window, qtbot)
    configure(d)
    d.open_preview("web")
    assert d.browser is not None
    qtbot.waitUntil(
        lambda: d.browser.view.url().scheme() == "cyberforge", timeout=10000
    )
    assert d.browser.rendered is not None
    assert d.browser.profile.isOffTheRecord()
    d.reject()
    assert d.browser is None
    d.force_close()
    assert d.state is None


@pytest.mark.parametrize("selection", ["empty", "unauthorized", "stale"])
def test_f8_01_actual_publish_button_requires_authorized_groups(
    integration_window, qtbot, monkeypatch, selection
):
    from sqlalchemy import text

    window = integration_window
    e = window.test_env
    d = dialog(window, qtbot)
    configure(d)
    if selection == "empty":
        d.groups.item(0).setCheckState(Qt.CheckState.Unchecked)
    elif selection == "unauthorized":
        group = GroupService(e.accounts).save_group(
            e.tokens["admin"], "Чужа група", instructors=(), learners=()
        )
        # Simulates a stale/forged UI picker; service permissions remain authoritative.
        d.groups.item(0).setData(Qt.ItemDataRole.UserRole, group.id)
        d.check_readiness()
    else:
        GroupService(e.accounts).set_members(e.tokens["admin"], e.group.id, (), ())
    assert d.report.technical_ready and not d.report.final_ready
    d.ack.setChecked(True)
    confirmations = []
    monkeypatch.setattr(
        d, "final_confirmation", lambda: confirmations.append(True) or True
    )
    d.navigate(2)
    qtbot.mouseClick(d.publish_button, Qt.MouseButton.LeftButton)
    assert not confirmations
    assert not d.publish_button.isEnabled()
    # Direct slot calls must also be safe even if UI enablement is bypassed.
    assert d.publish() is False
    assert "груп" in d.message.text()
    with e.database.engine.connect() as db:
        assert (
            db.execute(text("SELECT count(*) FROM publication_reviews")).scalar_one()
            == 0
        )
        assert (
            db.execute(text("SELECT count(*) FROM scenario_publications")).scalar_one()
            == 0
        )


def two_publications(window, qtbot, monkeypatch):
    e = window.test_env
    first_dialog = dialog(window, qtbot)
    configure(first_dialog)
    first_dialog.ack.setChecked(True)
    monkeypatch.setattr(first_dialog, "final_confirmation", lambda: True)
    assert first_dialog.publish()
    first = first_dialog.publications.history(window._token, e.scenario.id)[0]
    first_dialog.reject()
    page = window.scenario_page
    published = window.scenarios.get(window._token, e.scenario.id)
    draft = window.scenarios.create_next_draft(window._token, published)
    ew = window.emails.load(window._token, draft)
    window.emails.save(window._token, ew, window.emails.generate(window._token, ew))
    ww = page.webs.load(window._token, draft)
    page.webs.save(window._token, ww, page.webs.generate(window._token, ww))
    second_group = GroupService(e.accounts).save_group(
        e.tokens["admin"],
        "Друга група UI",
        instructors=(e.accounts.current(window._token).id,),
        learners=(),
    )
    page.load(draft, editable=True)
    second_dialog = dialog(window, qtbot)
    configure(second_dialog)
    second_dialog.groups.item(0).setCheckState(Qt.CheckState.Unchecked)
    second_dialog.groups.item(1).setCheckState(Qt.CheckState.Checked)
    second_dialog.ack.setChecked(True)
    monkeypatch.setattr(second_dialog, "final_confirmation", lambda: True)
    assert second_dialog.publish()
    second = second_dialog.publications.history(window._token, e.scenario.id)[0]
    second_dialog.reject()
    page.load(window.scenarios.get(window._token, e.scenario.id), editable=True)
    return first, second, second_group


def test_f8_02_historical_reload_keeps_publication_target(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    first, second, second_group = two_publications(window, qtbot, monkeypatch)
    d = dialog(window, qtbot)
    d.history.setCurrentIndex(d.history.findData(first.id))
    d.load_history()
    assert d.expected.version == 1
    assert d.mail.draft.scenario_version == 1
    assert d.history.currentData() == first.id
    d.load()
    assert d.history.currentData() == first.id
    assert (
        d.grant_groups.item(0).data(Qt.ItemDataRole.UserRole).group_id
        == window.test_env.group.id
    )


def test_f8_01_groups_revalidated_after_final_dialog(
    integration_window, qtbot, monkeypatch
):
    from sqlalchemy import text

    window = integration_window
    e = window.test_env
    d = dialog(window, qtbot)
    configure(d)
    d.ack.setChecked(True)

    def stale_during_confirmation():
        GroupService(e.accounts).set_members(e.tokens["admin"], e.group.id, (), ())
        return True

    monkeypatch.setattr(d, "final_confirmation", stale_during_confirmation)
    d.navigate(2)
    qtbot.mouseClick(d.publish_button, Qt.MouseButton.LeftButton)
    assert "груп" in d.message.text()
    with e.database.engine.connect() as db:
        assert (
            db.execute(text("SELECT count(*) FROM publication_reviews")).scalar_one()
            == 0
        )
        assert (
            db.execute(text("SELECT count(*) FROM scenario_publications")).scalar_one()
            == 0
        )


def test_f8_02_grant_confirmation_tracks_exact_publication_and_group(
    integration_window, qtbot, monkeypatch
):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    window = integration_window
    e = window.test_env
    first, second, second_group = two_publications(window, qtbot, monkeypatch)
    d = dialog(window, qtbot)
    publications = d.publications
    before = {
        p.id: (
            p,
            d.integration.inspect(
                window._token,
                window.scenarios.get(
                    window._token,
                    e.scenario.id,
                    version=p.manifest.snapshot.scenario_version,
                ),
            ),
        )
        for p in (first, second)
    }

    def assert_target(publication, group_id):
        assert d.history.currentData() == publication.id
        assert d.expected.version == publication.manifest.snapshot.scenario_version
        assert d.mail.draft.scenario_version == d.expected.version
        assert d.state.web.scenario_version == d.expected.version
        assert (
            d.grant_groups.item(0).data(Qt.ItemDataRole.UserRole).group_id == group_id
        )
        assert all(
            event.publication_id == publication.id
            for event in publications.audit(window._token, publication.id)
        )

    assert_target(second, second_group.id)
    d.history.setCurrentIndex(d.history.findData(first.id))
    assert_target(first, e.group.id)  # Selection itself synchronizes previews/context.
    d.refresh_grants()
    d.load()
    assert_target(first, e.group.id)
    d.reject()
    window.scenario_page.load(
        window.scenarios.get(window._token, e.scenario.id, version=1), editable=True
    )
    d = dialog(window, qtbot)
    assert_target(first, e.group.id)
    d.show_history()
    scroll = d.history_view
    d.grant_groups.setCurrentRow(0)
    scroll.ensureWidgetVisible(d.revoke_grant)
    confirmations = []

    def respond(accept):
        box = next(
            w
            for w in QApplication.topLevelWidgets()
            if isinstance(w, QMessageBox) and w.isVisible()
        )
        confirmations.append(box.text())
        button = next(
            b
            for b in box.buttons()
            if box.buttonRole(b)
            == (
                QMessageBox.ButtonRole.AcceptRole
                if accept
                else QMessageBox.ButtonRole.RejectRole
            )
        )
        button.click()

    # Real Qt modal cancel must preserve both sets of grants/audit.
    QTimer.singleShot(0, lambda: respond(False))
    qtbot.mouseClick(d.revoke_grant, Qt.MouseButton.LeftButton)
    assert len(publications.audit(window._token, first.id)) == 1
    assert len(publications.audit(window._token, second.id)) == 1
    QTimer.singleShot(0, lambda: respond(True))
    qtbot.mouseClick(d.revoke_grant, Qt.MouseButton.LeftButton)
    assert f"сценарій {e.scenario.id}" in confirmations[-1]
    assert f"версія 1, публікація {first.id}" in confirmations[-1]
    assert f"навчальна група {e.group.id}" in confirmations[-1]
    assert [g.active for g in publications.grants(window._token, first.id)] == [False]
    assert [g.active for g in publications.grants(window._token, second.id)] == [True]
    d.available_group.setCurrentIndex(d.available_group.findData(e.group.id))
    scroll.ensureWidgetVisible(d.add_grant)
    QTimer.singleShot(0, lambda: respond(True))
    qtbot.mouseClick(d.add_grant, Qt.MouseButton.LeftButton)
    assert [a.operation for a in publications.audit(window._token, first.id)] == [
        "grant",
        "revoke",
        "grant",
    ]
    d.history.setCurrentIndex(d.history.findData(second.id))
    assert_target(second, second_group.id)
    d.history.setCurrentIndex(d.history.findData(first.id))
    assert_target(first, e.group.id)

    # A selection change while the confirmation is open cannot redirect the write.
    d.grant_groups.setCurrentRow(0)

    def switch_during_confirmation(publication, group_id, active):
        assert publication.id == first.id and group_id == e.group.id and not active
        d.history.setCurrentIndex(d.history.findData(second.id))
        return True

    monkeypatch.setattr(d, "confirm_grant", switch_during_confirmation)
    d.change_grant(False)
    assert "Зміни доступу не виконано" in d.message.text()
    assert len(publications.audit(window._token, first.id)) == 3
    assert len(publications.audit(window._token, second.id)) == 1
    for p in (first, second):
        assert before[p.id] == (
            p,
            d.integration.inspect(
                window._token,
                window.scenarios.get(
                    window._token,
                    e.scenario.id,
                    version=p.manifest.snapshot.scenario_version,
                ),
            ),
        )
    assert publications.history(window._token, e.scenario.id) == (second, first)


def test_f8_02_history_selection_respects_unsaved_remain_and_discard(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    first, second, _ = two_publications(window, qtbot, monkeypatch)
    page = window.scenario_page
    draft = window.scenarios.create_next_draft(
        window._token, window.scenarios.get(window._token, window.test_env.scenario.id)
    )
    page.load(draft, editable=True)
    d = dialog(window, qtbot)
    assert d.history.currentData() is None
    assert not d.add_grant.isEnabled() and not d.revoke_grant.isEnabled()
    d.link_label.setText("Незбережений зв’язок нової версії")
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    d.history.setCurrentIndex(d.history.findData(first.id))
    assert d.expected == draft and d.dirty
    assert d.history.currentData() is None
    assert not d.add_grant.isEnabled() and not d.revoke_grant.isEnabled()
    assert d.grant_groups.count() == 0 and d.audit_text.toPlainText() == ""
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    d.history.setCurrentIndex(d.history.findData(second.id))
    assert d.expected.version == 2 and d.history.currentData() == second.id
    assert d.mail.draft.scenario_version == 2 and not d.dirty


def test_actual_constructor_button_repeated_web_preview_lifecycle(
    integration_window, qtbot, monkeypatch
):
    from PySide6.QtCore import QTimer
    from shiboken6 import isValid

    from cyberforge.ui.web_browser import WebBrowser

    window = integration_window
    page = window.scenario_page
    saved = page.integration.inspect(window._token, page.scenario)
    loads, terminations, disposed = [], [], []
    original_init = WebBrowser.__init__
    state = dict(
        cycle=0,
        opening=False,
        dialog=None,
        switches=0,
        content=False,
        done=False,
        error=None,
    )

    def observed_init(browser, *args, **kwargs):
        original_init(browser, *args, **kwargs)
        browser.page.loadFinished.connect(loads.append)
        browser.page.renderProcessTerminated.connect(
            lambda status, code: terminations.append((status, code))
        )

    monkeypatch.setattr(WebBrowser, "__init__", observed_init)
    driver = QTimer(window)
    driver.setInterval(50)

    def tick():
        try:
            d = state["dialog"]
            if d is not None:
                assert isValid(d), "Web initialization destroyed the integration dialog"
            else:
                dialogs = [
                    d for d in page.findChildren(IntegrationDialog) if d.isVisible()
                ]
                if not dialogs:
                    if state["cycle"] == 3:
                        state["done"] = True
                        driver.stop()
                    elif not state["opening"]:
                        state["opening"] = True
                        # A separate timer can drive the old nested exec loop too.
                        QTimer.singleShot(0, page.integration_button.click)
                    return
                d = state["dialog"] = dialogs[0]
                d.open_preview("web")
                return
            if len(loads) <= state["cycle"]:
                return
            assert loads[-1] is True
            browser = d.browser
            if not state["content"]:
                browser.page.toPlainText(
                    lambda text: state.update(content=bool(text and text.strip()))
                )
                return
            assert d.isVisible() and browser.profile.isOffTheRecord()
            if state["switches"] < 4:
                d.open_preview("email" if state["switches"] % 2 == 0 else "web")
                state["switches"] += 1
                return
            references = browser.view, browser.page, browser.profile
            d.reject()
            assert all(not isValid(value) for value in references)
            disposed.append(d)
            state.update(
                cycle=state["cycle"] + 1,
                opening=False,
                dialog=None,
                switches=0,
                content=False,
            )
        except Exception as error:
            state.update(error=error, done=True)
            driver.stop()
            d = state["dialog"]
            if d is not None and isValid(d):
                d.force_close()

    driver.timeout.connect(tick)
    driver.start()
    try:
        qtbot.waitUntil(lambda: state["done"], timeout=30000)
    finally:
        driver.stop()
    assert state["error"] is None, str(state["error"])
    qtbot.waitUntil(lambda: all(not isValid(d) for d in disposed))
    assert state["cycle"] == 3 and terminations == [] and window.isVisible()
    assert page.integration.inspect(window._token, page.scenario) == saved


def test_production_dialog_close_signout_and_unsaved_guards(
    integration_window, qtbot, monkeypatch
):
    from shiboken6 import isValid

    window = integration_window
    page = window.scenario_page
    page.open_integration()
    d = page.integration_dialog
    assert d is not None and d.isVisible()
    page.open_integration()
    assert page.integration_dialog is d
    d.link_label.setText("Незбережений зв’язок")
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    d.close()
    assert d.isVisible() and page.integration_dialog is d
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    d.close()
    qtbot.waitUntil(lambda: not isValid(d))
    assert page.integration_dialog is None
    page.open_integration()
    reopened = page.integration_dialog
    assert reopened is not None
    window._signed_out()
    qtbot.waitUntil(lambda: not isValid(reopened))
    assert page.integration_dialog is None and page.scenario is None


def test_renderer_diagnostics_are_safe_and_preview_only(
    integration_window, qtbot, caplog
):
    from PySide6.QtWebEngineCore import QWebEnginePage

    window = integration_window
    page = window.scenario_page
    before = page.integration.inspect(window._token, page.scenario)
    page.open_integration()
    d = page.integration_dialog
    d.open_preview("web")
    browser = d.browser
    done = []
    browser.page.loadFinished.connect(done.append)
    qtbot.waitUntil(lambda: bool(done) and done[-1] is True, timeout=15000)
    # Qt6.10 cannot synthesize this enum-valued C++ signal through emit().
    # Real signal delivery is covered by the separate renderer-process test.
    browser._renderer_terminated(
        QWebEnginePage.RenderProcessTerminationStatus.CrashedTerminationStatus, 17
    )
    assert browser.render_failed and "завершив роботу" in browser.feedback.text()
    assert "status=CrashedTerminationStatus exit_code=17" in caplog.text
    assert browser.draft.page.display_url not in caplog.text
    assert d.isVisible() and window.isVisible()
    with qtbot.waitSignal(browser.page.loadFinished, timeout=15000) as reloaded:
        browser.reload_current()
    assert reloaded.args == [True] and not browser.render_failed
    # Fail the actual owned document resource, rather than synthesizing the
    # legacy boolean signal also emitted for intentional action cancellation.
    browser.profile.removeUrlSchemeHandler(browser.handler)
    with qtbot.waitSignal(browser.page.loadFinished, timeout=15000) as failed:
        browser.reload_current()
    assert failed.args == [False]
    qtbot.waitUntil(lambda: "Не вдалося завантажити" in browser.feedback.text())
    assert browser.render_failed
    assert page.integration.inspect(window._token, page.scenario) == before
    d.reject()


@pytest.mark.skipif(os.name != "posix", reason="POSIX renderer signal only")
def test_actual_renderer_termination_recovery_preserves_application_and_sources(
    integration_window, qtbot
):
    import os
    import signal

    window = integration_window
    page = window.scenario_page
    before = page.integration.inspect(window._token, page.scenario)
    page.open_integration()
    d = page.integration_dialog
    d.open_preview("web")
    browser = d.browser
    loaded = []
    browser.page.loadFinished.connect(loaded.append)
    qtbot.waitUntil(lambda: bool(loaded) and loaded[-1] is True, timeout=15000)
    text = []
    browser.page.toPlainText(text.append)
    qtbot.waitUntil(lambda: bool(text) and bool(text[-1].strip()), timeout=15000)
    renderer_pid = browser.page.renderProcessPid()
    assert renderer_pid > 0 and renderer_pid != os.getpid()
    from pathlib import Path

    process = Path(f"/proc/{renderer_pid}")
    if process.is_dir():
        assert b"--no-sandbox" not in (process / "cmdline").read_bytes().split(b"\0")
        status = dict(
            line.split(":", 1) for line in (process / "status").read_text().splitlines()
        )
        assert status["Seccomp"].strip() == "2"
        assert status["NoNewPrivs"].strip() == "1"
    with qtbot.waitSignal(browser.page.renderProcessTerminated, timeout=10000):
        os.kill(
            renderer_pid, signal.SIGTERM
        )  # This view's own child, never a guessed PID.
    assert d.isVisible() and window.isVisible() and browser.render_failed
    assert "завершив роботу" in browser.feedback.text()
    with qtbot.waitSignal(browser.page.loadFinished, timeout=15000) as loaded:
        browser.reload_current()
    assert loaded.args == [True] and not browser.render_failed
    assert browser.page.renderProcessPid() != renderer_pid
    assert page.integration.inspect(window._token, page.scenario) == before
    d.reject()


def test_redesign_three_steps_free_navigation_and_readonly_details(
    integration_window, qtbot
):
    from PySide6.QtWidgets import QTabWidget

    d = dialog(integration_window, qtbot)
    assert d.windowTitle() == "Підготовка сценарію"
    assert len(d.step_buttons) == 3
    assert not d.findChildren(QTabWidget)
    assert d.browser is None
    for i in (2, 0, 1, 2):
        d.step_buttons[i].click()
        assert d.content.currentWidget() is d.steps[i]
        assert d.step_buttons[i].isChecked()
        assert "Поточний крок" in d.step_buttons[i].accessibleDescription()
        assert not d.publish_button.isEnabled()
    d.navigate(0)
    assert not d.target.isEnabled()
    assert d.target.currentData() == d.state.web.page.internal_resource_id
    assert not d.material_details.content.isVisible()
    d.material_details.toggle.click()
    assert d.material_details.content.isVisible()
    assert str(d.state.checked_sources["email_revision"]) in d.source_details.text()
    assert d.material_labels["email"].text().startswith(d.state.email.artifact.subject)
    assert d.material_labels["web"].text().startswith(d.state.web.page.tab_title)
    assert not d.technical_results.content.isVisible()


@pytest.mark.parametrize("destination", ["step", "preview", "constructor"])
def test_redesign_unsaved_navigation_remain_discard_and_save(
    integration_window, qtbot, monkeypatch, destination
):
    window = integration_window
    d = dialog(window, qtbot)
    before = d.integration.inspect(window._token, d.expected)
    d.link_label.setText("Незбережена правка")
    requested = []
    d.constructor_requested.connect(requested.append)
    actions = {
        "step": lambda: d.navigate(1),
        "preview": lambda: d.open_preview("email"),
        "constructor": lambda: d.request_constructor("email"),
    }
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    actions[destination]()
    assert d.content.currentWidget() is d.materials_step and d.dirty
    assert not requested
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    actions[destination]()
    assert not d.dirty
    assert d.integration.inspect(window._token, d.expected) == before
    if destination == "constructor":
        assert requested == ["email"] and not d.isVisible()
    else:
        assert d.isVisible()
        if destination == "preview":
            d.go_back()
        d.navigate(0)
        d.link_label.setText("Явно збережено при переході")
        monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Save)
        d.navigate(1)
        after = d.integration.inspect(window._token, d.expected)
        assert after.link.link_label == "Явно збережено при переході"
        assert (after.email, after.web) == (before.email, before.web)


def test_redesign_rubric_groups_precision_preset_and_unsaved_guard(
    integration_window, qtbot, monkeypatch
):
    from cyberforge.scenario_integration.contracts import CRITERIA

    d = dialog(integration_window, qtbot)
    d.navigate(1)
    assert set(d.criteria) == {c.id for c in CRITERIA}
    for spec in CRITERIA:
        assert spec.id in d.criterion_groups[spec.phase]
        _, weight, applicability = d.criteria[spec.id]
        assert (
            tuple(applicability.itemData(i) for i in range(applicability.count()))
            == spec.applicability
        )
        assert weight.validator() is not None
        assert not d.criterion_details[spec.id].content.isVisible()
    d.apply_preset()
    assert d.dirty and d.state.rubric is None
    qtbot.wait(30)
    viewport = d.rubric_step.viewport()
    last_criterion = d.criteria["web.report"][0]
    assert viewport.rect().contains(
        last_criterion.mapTo(viewport, last_criterion.rect().bottomRight())
    )
    assert "Обрано 8 із 8" in d.rubric_summary.text()
    assert "Підтримується безпечний шлях" in d.rubric_summary.text()
    assert d.integration.inspect(d.session_token, d.expected).rubric is None
    d.criteria["email.sender"][1].setText("0.000000000123")
    assert d.save_rubric()
    saved = d.state.rubric
    d.load()
    assert float(d.criteria["email.sender"][1].text()) == 0.000000000123
    monkeypatch.setattr(d, "confirm_preset", lambda: False)
    d.apply_preset()
    assert not d.dirty and d.state.rubric == saved
    monkeypatch.setattr(d, "confirm_preset", lambda: True)
    d.apply_preset()
    assert d.dirty and d.state.rubric == saved
    assert d.integration.inspect(d.session_token, d.expected).rubric == saved
    for identifier, (enabled, _, _) in d.criteria.items():
        enabled.setChecked(identifier.startswith("web."))
    assert "Додайте критерій" in d.rubric_summary.text()
    assert not d.save_rubric()
    assert not d.publish_button.isEnabled()


@pytest.mark.parametrize("value", ["0", "-1", "inf", "nan", "10000.1", "abc"])
def test_redesign_invalid_weights_do_not_replace_saved_rubric(
    integration_window, qtbot, value
):
    d = dialog(integration_window, qtbot)
    d.criteria["email.sender"][0].setChecked(True)
    assert d.save_rubric()
    saved = d.state.rubric
    d.criteria["email.sender"][1].setText(value)
    assert not d.save_rubric()
    assert "Вага" in d.message.text()
    assert d.integration.inspect(d.session_token, d.expected).rubric == saved


def test_redesign_missing_stale_materials_and_contextual_corrections(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    page = window.scenario_page
    e = window.test_env
    empty = window.scenarios.create(
        window._token, dict(topic="Без матеріалів", difficulty="beginner")
    )
    page.load(empty, editable=True)
    page.open_integration()
    d = page.integration_dialog
    assert not d.preview_buttons["email"].isEnabled()
    assert not d.preview_buttons["web"].isEnabled()
    assert d.target.currentData() is None and not d.save_link_button.isEnabled()
    assert "не збережено" in d.status_summary.text()
    d.navigate(2)
    from PySide6.QtWidgets import QPushButton

    d.check_rows["rubric"].findChild(QPushButton).click()
    assert d.content.currentWidget() is d.rubric_step
    d.navigate(2)
    d.check_rows["email"].findChild(QPushButton).click()
    assert page.integration_dialog is None
    assert page.content_stack.currentWidget() is page.email_page
    assert page.email_page.workspace.draft is None
    # Re-saving the original Email invalidates its saved Web without replacing it.
    page.load(e.scenario, editable=True)
    ew = window.emails.load(window._token, e.scenario)
    window.emails.save(window._token, ew, ew.draft)
    stale = dialog(window, qtbot)
    assert stale.state.web is None
    assert "потребує оновлення" in stale.material_labels["web"].text().lower()
    assert not stale.open_preview("web") and stale.browser is None


def test_redesign_readiness_warnings_attestation_and_source_invalidation(
    integration_window, qtbot, monkeypatch
):
    d = dialog(integration_window, qtbot)
    configure(d)
    d.display_url.setText("https://different.training.invalid/review")
    assert "Адреса в листі відрізняється" in d.url_warning.text()
    assert d.save_link()
    d.navigate(2)
    assert d.report.technical_ready
    assert {"email", "web", "link", "rubric", "security"} <= set(d.check_rows)
    assert all(check.check_id in d.details.toPlainText() for check in d.report.checks)
    assert "display_url_mismatch" in d.report.acknowledgement_requirements
    assert "Відмінність адрес" in d.attestation_summary.text()
    assert not d.publish_button.isEnabled()
    d.ack.setChecked(True)
    assert d.publish_button.isEnabled()
    d.link_label.setText("Нова назва")
    assert not d.ack.isChecked() and not d.publish_button.isEnabled()
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Discard)
    d.navigate(0)
    d.ack.setChecked(True)
    ew = integration_window.emails.load(d.session_token, d.expected)
    integration_window.emails.save(d.session_token, ew, ew.draft)
    d._check_external_changes()
    assert d.report is None and not d.ack.isChecked()
    assert not d.publish_button.isEnabled()
    assert "змінилися" in d.status_summary.text()


def test_redesign_history_entry_from_new_draft_and_exact_preview(
    integration_window, qtbot, monkeypatch
):
    from shiboken6 import isValid

    window = integration_window
    page = window.scenario_page
    assert not page.publications_button.isVisible()
    first, second, _ = two_publications(window, qtbot, monkeypatch)
    draft = window.scenarios.create_next_draft(
        window._token, window.scenarios.get(window._token, page.scenario.id)
    )
    page.load(draft, editable=True)
    assert page.publications_button.isVisible()
    page.publications_button.click()
    d = page.integration_dialog
    assert d.content.currentWidget() is d.history_view
    assert d.expected.version == 2 and d.history.currentData() == second.id
    d.history.setCurrentIndex(d.history.findData(first.id))
    assert d.expected.version == 1
    before = d.integration.inspect(window._token, d.expected)
    d.open_history.click()
    assert d.content.currentWidget() is d.mail
    assert d.mail.draft == before.email and d.state.rubric == before.rubric
    assert d.state.link == before.link and d.link_label.isReadOnly()
    assert d.published_definition.isReadOnly()
    d.go_back()
    assert d.content.currentWidget() is d.history_view
    assert "Перевірка відправника" in d.published_definition.toPlainText()
    assert not d.audit_details.content.isVisible()
    assert "Доступ надано" in d.grant_groups.item(0).text()
    assert d.integration.inspect(window._token, d.expected) == before
    d.close()
    qtbot.waitUntil(lambda: not isValid(d))
    assert page.scenario == draft


def test_redesign_account_switch_guard_preserves_unsaved_editor(
    integration_window, qtbot, monkeypatch
):
    window = integration_window
    window.scenario_page.open_integration()
    d = window.scenario_page.integration_dialog
    d.link_label.setText("Правка перед виходом")
    monkeypatch.setattr(d, "ask_unsaved", lambda: QMessageBox.StandardButton.Cancel)
    assert not window.scenario_page.can_leave()
    assert d.dirty and d.isVisible()
    # Forced expiration must clear private buffers without saving through an old token.
    window._signed_out()
    assert d.forced and d.state is None and d.link_label.text() == ""


def test_redesign_end_to_end_result_and_screenshot_states(
    integration_window, qtbot, monkeypatch
):
    from pathlib import Path

    window = integration_window
    page = window.scenario_page
    page.integration_button.click()
    d = page.integration_dialog
    screenshot_dir = os.environ.get("CYBERFORGE_UX_SCREENSHOTS")

    def capture(name):
        qtbot.wait(80)
        if screenshot_dir:
            folder = Path(screenshot_dir)
            folder.mkdir(parents=True, exist_ok=True)
            assert d.grab().save(str(folder / f"phase-8-ux-{name}.png"))

    assert d.save_link()
    capture("materials")
    d.navigate(1)
    d.apply_preset()
    assert d.save_rubric()
    capture("rubric")
    d.navigate(2)
    d.groups.item(0).setCheckState(Qt.CheckState.Checked)
    capture("publication")
    before = d.integration.inspect(window._token, d.expected)
    d.open_preview("email")
    capture("email")
    d.go_back()
    d.open_preview("web")
    loaded = []
    d.browser.page.loadFinished.connect(loaded.append)
    qtbot.waitUntil(lambda: bool(loaded) and loaded[-1], timeout=15000)
    capture("web")
    d.go_back()
    assert d.integration.inspect(window._token, d.expected) == before
    d.navigate(2)
    d.ack.setChecked(True)
    monkeypatch.setattr(d, "final_confirmation", lambda: True)
    assert d.publish(), d.message.text()
    assert d.content.currentWidget() is d.result_view
    assert "захищені від змін" in d.result_summary.text()
    assert "Група UI" in d.result_summary.text()
    capture("result")
    d.view_publication.click()
    assert d.content.currentWidget() is d.history_view
    assert not d.writable and d.history.currentData() is not None
    capture("history")


def test_redesign_actual_final_confirmation_cancel_and_publish(
    integration_window, qtbot
):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    d = dialog(integration_window, qtbot)
    configure(d)
    d.navigate(2)
    d.ack.setChecked(True)
    confirmations = []

    def respond(accept):
        box = next(
            w
            for w in QApplication.topLevelWidgets()
            if isinstance(w, QMessageBox) and w.isVisible()
        )
        confirmations.append(box.text())
        role = (
            QMessageBox.ButtonRole.AcceptRole
            if accept
            else QMessageBox.ButtonRole.RejectRole
        )
        next(
            button for button in box.buttons() if box.buttonRole(button) == role
        ).click()

    QTimer.singleShot(0, lambda: respond(False))
    qtbot.mouseClick(d.publish_button, Qt.MouseButton.LeftButton)
    assert d.expected.status == "draft" and d.ack.isChecked()
    assert not d.publications.history(d.session_token, d.expected.id)
    assert f"Сценарій {d.expected.id}, версія 1" in confirmations[-1]
    assert "Група UI" in confirmations[-1] and "незмінним" in confirmations[-1]
    QTimer.singleShot(0, lambda: respond(True))
    qtbot.mouseClick(d.publish_button, Qt.MouseButton.LeftButton)
    assert d.expected.status == "published"
    assert d.content.currentWidget() is d.result_view


@pytest.mark.parametrize("card_minimum", [0, 420])
def test_redesign_resizing_keyboard_and_responsive_cards(
    integration_window, qtbot, monkeypatch, card_minimum
):
    from PySide6.QtWidgets import QBoxLayout, QCheckBox

    if card_minimum:
        from cyberforge.ui import scenario_integration

        class NativeCheckBox(QCheckBox):
            def minimumSizeHint(self):
                hint = super().minimumSizeHint()
                if "\n" in self.text():
                    hint.setWidth(max(668, hint.width()))
                return hint

        monkeypatch.setattr(scenario_integration, "QCheckBox", NativeCheckBox)
    d = dialog(integration_window, qtbot)
    # Reproduce Windows native minimum-size pressure without changing fonts.
    for i in range(d.material_cards.cards_layout.count()):
        d.material_cards.cards_layout.itemAt(i).widget().setMinimumWidth(card_minimum)
    for width, height in ((960, 680), (600, 580), (960, 680)):
        d.resize(width, height)
        for index in range(3):
            assert d.navigate(index)
            qtbot.wait(30)
            scroll = d.steps[index]
            assert scroll.widget().width() <= scroll.viewport().width(), (
                width,
                index,
                scroll.widget().minimumSizeHint(),
            )
            assert d.width() <= width
            for control in (
                d.back_button,
                d.next_button,
                d.save_link_button,
                d.save_rubric_button,
                d.publish_button,
                d.close_buttons,
            ):
                if control.isVisible():
                    assert d.rect().contains(
                        control.mapTo(d, control.rect().bottomRight())
                    ), (
                        width,
                        index,
                        control.text() if hasattr(control, "text") else "Close",
                    )
        d.navigate(0)
        qtbot.wait(30)
        assert d.material_cards.cards_layout.direction() == (
            QBoxLayout.Direction.TopToBottom
            if width == 600
            else QBoxLayout.Direction.LeftToRight
        )
    d.step_buttons[1].setFocus()
    qtbot.keyClick(d.step_buttons[1], Qt.Key.Key_Space)
    assert d.content.currentWidget() is d.rubric_step
    disclosure = d.criterion_details["email.sender"]
    disclosure.toggle.setFocus()
    qtbot.keyClick(disclosure.toggle, Qt.Key.Key_Space)
    assert disclosure.content.isVisible()
    assert disclosure.toggle.accessibleDescription() == "Розгорнуто"
    d.navigate(2)
    d.publication_step.ensureWidgetVisible(d.ack_label)
    d.groups.item(0).setCheckState(Qt.CheckState.Checked)
    assert not d.ack.isChecked()
    qtbot.mouseClick(d.ack_label, Qt.MouseButton.LeftButton)
    assert d.ack.isChecked() and d.focusWidget() is d.ack
    qtbot.keyClick(d.ack, Qt.Key.Key_Space)
    assert not d.ack.isChecked()


def test_redesign_group_assignment_changes_clear_picker_and_acknowledgement(
    integration_window, qtbot
):
    window = integration_window
    d = dialog(window, qtbot)
    configure(d)
    d.ack.setChecked(True)
    assert d.publish_button.isEnabled()
    GroupService(window.test_env.accounts).set_members(
        window.test_env.tokens["admin"], window.test_env.group.id, (), ()
    )
    d._check_external_changes()
    assert d.groups.count() == d.available_group.count() == 0
    assert not d.ack.isChecked() and not d.publish_button.isEnabled()
    assert "Виберіть хоча б одну" in d.group_hint.text()
    assert not d.publish()


@pytest.mark.parametrize("enabled", [True, False])
def test_group_indicator_remains_visible_when_selected(
    integration_window, qtbot, enabled
):
    from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

    d = dialog(integration_window, qtbot)
    configure(d)
    d.navigate(2)
    picker = d.groups
    picker.setEnabled(enabled)
    d.publication_step.ensureWidgetVisible(picker)
    item = picker.item(0)
    index = picker.model().index(0, 0)
    captures = {}
    for selected in (False, True):
        picker.setCurrentRow(0)
        picker.setFocus()
        if not selected:
            picker.clearSelection()
        for checked in (False, True):
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            qtbot.wait(30)
            option = QStyleOptionViewItem()
            option.initFrom(picker)
            picker.itemDelegate().initStyleOption(option, index)
            option.rect = picker.visualItemRect(item)
            rect = picker.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, picker
            )
            captures[selected, checked] = picker.viewport().grab(rect).toImage()
            if os.environ.get("CYBERFORGE_GROUP_SCREENSHOTS"):
                from pathlib import Path

                folder = Path(os.environ["CYBERFORGE_GROUP_SCREENSHOTS"])
                folder.mkdir(parents=True, exist_ok=True)
                picker.grab().save(
                    str(folder / f"group-{enabled}-{selected}-{checked}.png")
                )
            assert d.selected_groups() == (
                (item.data(Qt.ItemDataRole.UserRole),) if checked else ()
            )
        picker.clearSelection()
        assert item.checkState() == Qt.CheckState.Checked
    for selected in (False, True):

        def bright(image):
            return sum(
                image.pixelColor(x, y).lightness() > 150
                for x in range(3, image.width() - 3)
                for y in range(3, image.height() - 3)
            )

        assert bright(captures[selected, True]) >= bright(captures[selected, False]) + 4
    picker.setEnabled(True)
    picker.setCurrentRow(0)
    picker.setFocus()
    qtbot.keyClick(picker, Qt.Key.Key_Space)
    assert item.checkState() == Qt.CheckState.Unchecked
    assert d.selected_groups() == ()
    qtbot.keyClick(picker, Qt.Key.Key_Space)
    assert item.checkState() == Qt.CheckState.Checked
