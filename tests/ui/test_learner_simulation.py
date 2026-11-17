"""Real Qt learner E2E paths with isolated immutable offline publications."""

import os

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QMessageBox

from cyberforge.ui.navigation import View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme
from tests.test_learner_attempts import learning_env  # noqa: F401
from tests.test_scenario_integration import publication_env  # noqa: F401


@pytest.fixture
def learner_window(qtbot, qapp, learning_env):  # noqa: F811
    e = learning_env
    apply_theme(qapp)
    window = MainWindow(e.accounts, e.emails, e.webs)
    qtbot.addWidget(window)
    window._authenticated(e.learner)
    window.navigate(View.MY_SCENARIOS)
    window.resize(1100, 720)
    window.show()
    window.test_env = e
    return window


def click(qtbot, item):
    assert item.isEnabled()
    qtbot.mouseClick(item, Qt.MouseButton.LeftButton)


def begin(window, qtbot):
    catalog = window.learner_catalog
    click(qtbot, catalog.info)
    click(qtbot, catalog.start)
    sim = catalog.simulation
    assert sim.controller is not None
    return sim


def open_main(sim, qtbot):
    rect = sim.mail.messages.visualItemRect(sim.mail.messages.item(0))
    qtbot.mouseClick(
        sim.mail.messages.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
    )
    # Accepted mailbox activates by double click or Enter.
    qtbot.keyClick(sim.mail.messages, Qt.Key.Key_Return)
    assert sim.controller.attempt.email_opened


def confirm(sim, qtbot, yes=True):
    qtbot.waitUntil(lambda: sim.confirmation is not None)
    click(
        qtbot,
        sim.confirmation.button(
            QMessageBox.StandardButton.Yes if yes else QMessageBox.StandardButton.No
        ),
    )
    qtbot.waitUntil(lambda: sim.confirmation is None)


def test_real_qt_safe_decline_history_and_repeat(learner_window, qtbot):
    w = learner_window
    e = w.test_env
    assert len(w.learner_catalog.rows) == 1
    assert not e.attempts.history(e.learner)
    click(qtbot, w.learner_catalog.info)
    assert not e.attempts.history(e.learner)
    click(qtbot, w.learner_catalog.start)
    sim = w.learner_catalog.simulation
    open_main(sim, qtbot)
    for item in (sim.sender, sim.link, sim.report):
        click(qtbot, item)
    click(qtbot, sim.decline)
    assert sim.controller.attempt.status == "IN_PROGRESS"
    confirm(sim, qtbot)
    a = sim.controller.attempt
    assert a.status == "COMPLETED" and not a.web_visited and sim.browser is None
    assert "завершили" in sim.feedback.text()
    w.navigate(View.MY_RESULTS)
    assert w.learner_history.list.count() == 1
    assert "Очікує оцінювання" in w.learner_history.list.item(0).text()
    w.navigate(View.MY_SCENARIOS)
    other = begin(w, qtbot)
    assert other.controller.attempt.attempt_id != a.attempt_id
    assert w.nav_buttons[View.CONSTRUCTOR].isHidden()
    assert w.nav_buttons[View.ADMIN].isHidden()


def test_real_web_navigation_actions_revocation_restore_resume(learner_window, qtbot):
    w, e = learner_window, learner_window.test_env
    sim = begin(w, qtbot)
    open_main(sim, qtbot)
    a = sim.controller.attempt
    click(qtbot, sim.mail.learner_link)
    qtbot.waitUntil(lambda sim=sim: sim.controller.attempt.web_visited, timeout=20000)
    browser = sim.browser
    assert browser.profile.isOffTheRecord()
    assert browser.page.url().scheme() == "cyberforge"
    assert browser.address.text() == sim.state.web.page.display_url
    # Native keyboard activation goes through Chromium and the trusted callback;
    # JavaScript stays disabled. The first published link is the hero confirm.
    native_load_outcomes = []
    browser.page.loadFinished.connect(native_load_outcomes.append)
    browser.view.setFocus()
    qtbot.keyClick(browser.view.focusProxy(), Qt.Key.Key_Tab)
    before_native = sim.controller.attempt.last_event_sequence
    qtbot.keyClick(browser.view.focusProxy(), Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: sim.controller.attempt.last_event_sequence > before_native)
    assert e.attempts.events(e.learner, a.attempt_id)[-1].action_id == "confirm"
    qtbot.waitUntil(lambda: False in native_load_outcomes)
    assert not browser.render_failed
    before_native = sim.controller.attempt.last_event_sequence
    qtbot.keyClick(browser.view.focusProxy(), Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: sim.controller.attempt.last_event_sequence > before_native)
    assert not browser.render_failed
    _, state = e.attempts.content(e.learner, a.attempt_id)
    pairs = [
        (c.id, action.id)
        for c in state.web.page.components
        for action in getattr(c, "actions", ())
    ]
    for component, action in pairs:
        if action == "leave":
            continue
        address = next(
            url
            for url in browser.store.actions
            if browser.store.actions[url] == action
            and browser.store.components[url] == component
        )
        before = sim.controller.attempt.last_event_sequence
        assert not browser.page.acceptNavigationRequest(
            QUrl(address), browser.page.NavigationType.NavigationTypeLinkClicked, True
        )
        assert sim.controller.attempt.last_event_sequence == before + 1
    e.publications.change_grant(
        e.token, a.publication_id, e.group.id, active=False, expected_revision=1
    )
    before = e.attempts.get(e.learner, a.attempt_id)
    sim._web_action(pairs[0][1], pairs[0][0])
    assert sim.controller is None and sim.browser is None
    assert "Доступ" in sim.feedback.text()
    assert e.attempts.history(e.learner)[0] == before
    e.publications.change_grant(
        e.token, a.publication_id, e.group.id, active=True, expected_revision=2
    )
    w.learner_catalog.show_catalog()
    sim = begin(w, qtbot)
    qtbot.waitUntil(lambda: sim._display_recorded, timeout=20000)
    assert sim.controller.attempt.attempt_id == a.attempt_id
    events = e.attempts.events(e.learner, a.attempt_id)
    assert sum(x.action_id == "open_internal" for x in events) == 1
    browser = sim.browser
    leave_url = next(
        url for url, action in browser.store.actions.items() if action == "leave"
    )
    assert not browser.page.acceptNavigationRequest(
        QUrl(leave_url), browser.page.NavigationType.NavigationTypeLinkClicked, True
    )
    confirm(sim, qtbot, yes=False)
    assert sim.controller.attempt.status == "IN_PROGRESS"
    assert browser.view.isVisible()
    assert not browser.page.acceptNavigationRequest(
        QUrl(leave_url), browser.page.NavigationType.NavigationTypeLinkClicked, True
    )
    confirm(sim, qtbot)
    assert sim.controller.attempt.status == "COMPLETED"
    assert e.attempts.events(e.learner, a.attempt_id)[-2].action_id == "leave"
    assert not sim.browser.gate.blocked


def test_decline_cancel_restart_and_session_stale_callback(learner_window, qtbot):
    w, e = learner_window, learner_window.test_env
    sim = begin(w, qtbot)
    open_main(sim, qtbot)
    click(qtbot, sim.decline)
    confirm(sim, qtbot, yes=False)
    a = sim.controller.attempt
    assert a.decision == "DECLINED" and a.status == "IN_PROGRESS"
    old_controller = sim.controller
    w._signed_out()
    assert not old_controller.active and sim.mail.draft is None
    w._authenticated(e.accounts.login("learner", e.password))
    w.navigate(View.MY_SCENARIOS)
    sim = begin(w, qtbot)
    assert sim.controller.attempt == a
    assert sim.complete.isEnabled()
    click(qtbot, sim.abandon)
    confirm(sim, qtbot)
    assert sim.controller.attempt.status == "ABANDONED"


def test_web_load_failure_does_not_record_visit(learner_window, qtbot, monkeypatch):
    from cyberforge.ui.web_browser import WebBrowser

    w = learner_window
    sim = begin(w, qtbot)
    open_main(sim, qtbot)
    # Exercise real browser creation while delaying the resource load, then
    # deliver Qt's failed load path. No fake successful-display event.
    original = WebBrowser.set_draft
    monkeypatch.setattr(WebBrowser, "set_draft", lambda self, draft: None)
    click(qtbot, sim.mail.learner_link)
    sim.browser._load_finished(False)
    assert not sim.controller.attempt.web_visited
    assert not sim.complete.isEnabled()
    assert sim.browser.render_failed
    original(sim.browser, sim.state.web)
    qtbot.waitUntil(lambda sim=sim: sim.controller.attempt.web_visited, timeout=20000)
    assert sim.complete.isEnabled()


def test_compact_keyboard_layout_and_repeated_lifecycle(
    learner_window, qtbot, tmp_path
):
    w = learner_window
    for cycle in range(3):
        sim = begin(w, qtbot)
        if cycle == 0:
            open_main(sim, qtbot)
            assert sim.complete.geometry().right() <= sim.width()
            assert sim.email_controls.geometry().right() <= sim.width()
            viewport = w.containers[View.MY_SCENARIOS].viewport()
            qtbot.wait(80)
            assert (
                sim.back.mapTo(viewport, sim.back.rect().bottomRight()).y()
                <= viewport.height()
            )
            assert sim.mail.body.viewport().height() >= 100
            qtbot.waitUntil(
                lambda sim=sim: sim.sender.isVisible() and sim.sender.isEnabled()
            )
            sim.sender.setFocus()
            if os.environ.get("CYBERFORGE_LEARNER_SCREENSHOTS"):
                from pathlib import Path

                folder = Path(os.environ["CYBERFORGE_LEARNER_SCREENSHOTS"])
                folder.mkdir(parents=True, exist_ok=True)
                qtbot.wait(200)  # allow native text layouts and WSLg paint
                w.grab().save(str(folder / "phase-9-email.png"))
            qtbot.keyClick(sim.sender, Qt.Key.Key_Space)
            assert "Відправник" in sim.feedback.text()
            click(qtbot, sim.mail.learner_link)
        qtbot.waitUntil(lambda sim=sim: sim._display_recorded, timeout=20000)
        assert sim.browser.width() <= sim.width()
        if os.environ.get("CYBERFORGE_LEARNER_SCREENSHOTS"):
            qtbot.wait(200)  # loadFinished precedes compositor presentation
            w.grab().save(str(folder / "phase-9-web.png"))
        click(qtbot, sim.back)
        assert sim.browser is None
        assert w.isVisible()
    assert len(w.test_env.attempts.history(w._token)) == 1


def test_regular_preset_native_controls(qtbot, qapp, publication_env):  # noqa: F811
    from cyberforge.application.learner_attempts import LearnerAttemptService
    from tests.test_scenario_integration import publish

    e = publication_env
    publication = publish(e)  # ordinary preset, no demo_web_actions helper
    e.learner = e.tokens["learner"]
    e.attempts = LearnerAttemptService(e.access)
    window = MainWindow(e.accounts, e.emails, e.webs)
    qtbot.addWidget(window)
    window._authenticated(e.learner)
    window.navigate(View.MY_SCENARIOS)
    window.show()
    sim = begin(window, qtbot)
    open_main(sim, qtbot)
    click(qtbot, sim.mail.learner_link)
    qtbot.waitUntil(lambda: sim._display_recorded, timeout=20000)
    before = e.access.content(e.learner, publication.id)[1].web.model_dump_json()
    assert not any(
        a.id == "inspect_address"
        for c in sim.state.web.page.components
        for a in getattr(c, "actions", ())
    )
    for action in ("inspect_address", "report", "leave"):
        sequence = sim.controller.attempt.last_event_sequence
        click(qtbot, sim.browser.control_buttons[action])
        assert sim.controller.attempt.last_event_sequence == sequence + 1
        event = e.attempts.events(e.learner, sim.controller.attempt.attempt_id)[-1]
        assert event.action_id == action and event.provenance == "browser_control"
    confirm(sim, qtbot)
    assert sim.controller.attempt.status == "COMPLETED"
    assert (
        e.access.content(e.learner, publication.id)[1].web.model_dump_json() == before
    )
