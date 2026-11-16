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
from cyberforge.ui.theme import apply_theme


@pytest.fixture
def integration_window(qtbot, qapp, scenario_env):
    env = scenario_env
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
    for index in (0, 1, 4, 5):
        d.tabs.setCurrentIndex(index)
        qtbot.wait(10)
        scroll = d.tabs.widget(index)
        assert scroll.widget().width() <= scroll.viewport().width()
        scroll.ensureWidgetVisible(
            d.publish_button
            if index == 4
            else d.save_rubric_button
            if index == 1
            else d.save_link_button
            if index == 0
            else d.audit_text
        )
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
    d.tabs.setCurrentIndex(3)
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
    d.tabs.setCurrentIndex(4)
    d.tabs.widget(4).ensureWidgetVisible(d.publish_button)
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
    d.tabs.setCurrentIndex(4)
    d.tabs.widget(4).ensureWidgetVisible(d.publish_button)
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
    d.tabs.setCurrentIndex(5)
    scroll = d.tabs.widget(5)
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
                d.tabs.setCurrentIndex(3)
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
                d.tabs.setCurrentIndex(2 if state["switches"] % 2 == 0 else 3)
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
    d.tabs.setCurrentIndex(3)
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
    browser.page.loadFinished.emit(False)
    assert "Не вдалося завантажити" in browser.feedback.text()
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
    d.tabs.setCurrentIndex(3)
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
