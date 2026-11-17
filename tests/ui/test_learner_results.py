"""Real learner results widgets over authorized production services and SQLite."""

import pytest
from PySide6.QtCore import Qt

from cyberforge.application.evaluations import EvaluationService
from cyberforge.application.learner_attempts import LearnerAttemptService
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.llm.factory import create_gateway
from cyberforge.ui.learner_results import LearnerResultsPage
from cyberforge.ui.theme import apply_theme
from tests.test_evaluation import bundle, frozen  # noqa: F401
from tests.test_evaluation_persistence import runtime  # noqa: F401
from tests.test_learner_attempts import (  # noqa: F401
    act,
    enter_web,
    learning_env,
    start,
)
from tests.test_scenario_integration import publication_env  # noqa: F401
from tests.ui.test_learner_simulation import learner_window  # noqa: F401


def page_for(e, qtbot, qapp):
    apply_theme(qapp)
    ev = EvaluationService(LearnerAttemptService(e.access))
    mentor = MentorFeedbackService(ev, create_gateway())
    page = LearnerResultsPage(ev, mentor, lambda: e.tokens["learner"])
    qtbot.addWidget(page)
    page.resize(680, 600)
    page.show()
    page.refresh()
    return page


def test_all_completed_paths_pending_score_feedback(
    qtbot,
    qapp,
    bundle,  # noqa: F811
    publication_env,  # noqa: F811
):
    name, evidence, expected, _, _ = bundle
    p = page_for(publication_env, qtbot, qapp)
    assert "Очікує оцінювання" in p.list.item(0).text()
    assert p.evaluate_button.isEnabled()
    # Actual keyboard activation, queued worker and database persistence.
    p.evaluate_button.setFocus()
    qtbot.keyClick(p.evaluate_button, Qt.Key.Key_Space)
    qtbot.waitUntil(lambda: not p.pending, timeout=10000)
    assert not p.evaluate_button.isEnabled()
    assert (
        p.evaluations.read(
            publication_env.tokens["learner"], evidence.attempt.attempt_id
        ).criteria
        == expected.criteria
    )
    assert "критичних порушень не налаштовано" in p.detail.text()
    assert "Навчальне пояснення" in p.feedback.text()
    if name == "unscorable":
        assert "UNSCORABLE" in p.detail.text() and "не нульова" in p.detail.text()
    elif name == "safe":
        assert "100.00%" in p.detail.text()
        assert "Не застосовується" in p.detail.text()
    elif name == "observations":
        assert "Надсилання синтетичної форми" in p.detail.text()
    assert not p.feedback_button.isEnabled()
    assert (
        p.mentor.read(publication_env.tokens["learner"], evidence.attempt.attempt_id)
        is not None
    )
    # Compact widgets stay in bounds; details scroll, actions stay available.
    for b in (p.refresh_button, p.evaluate_button, p.feedback_button):
        assert b.geometry().right() < p.width()
        assert b.geometry().bottom() < p.height()
    epoch = p.epoch
    p.invalidate()
    p._feedback_finished(epoch, evidence.attempt.attempt_id, "stale")
    assert not p.detail.text() and not p.feedback.text() and p.list.count() == 0


def test_empty_incomplete_abandoned_and_genuine_zero(qtbot, qapp, learning_env):  # noqa: F811
    e = learning_env
    p = page_for(e, qtbot, qapp)
    assert "ще не розпочали" in p.notice.text()
    a = start(e)
    p.refresh()
    assert "У процесі" in p.list.item(0).text()
    assert not p.evaluate_button.isEnabled()
    a = act(e, a, "system", "abandoned")
    p.refresh()
    assert "Припинено" in p.list.item(0).text()
    assert "Незавершена" in p.detail.text()
    a = enter_web(e, start(e))
    a = act(e, a, "system", "web_entered")
    a = act(e, a, "system", "completed")
    p.evaluations.evaluate(e.learner, a.attempt_id)
    p.refresh()
    index = next(
        i for i, r in enumerate(p.rows) if r.attempt.attempt_id == a.attempt_id
    )
    p.list.setCurrentRow(index)
    assert "0.00%" in p.detail.text()
    assert "ще не збережено" in p.feedback.text()
    assert p.feedback_button.isEnabled()


@pytest.mark.parametrize("role", ["admin", "teacher", "other", None])
def test_restricted_ui_clears_data(runtime, qtbot, qapp, role):  # noqa: F811
    e = runtime
    p = page_for(e, qtbot, qapp)
    e.ev.evaluate(e.learner, e.aid)
    p.refresh()
    assert p.list.count() == 1
    p.token_provider = lambda: e.tokens.get(role)
    p.refresh()
    assert p.list.count() == 0 and not p.detail.text() and not p.feedback.text()
    assert "Доступ" in p.notice.text()


@pytest.mark.parametrize("target", ["evaluation", "feedback"])
def test_integrity_states_fail_closed(runtime, qtbot, qapp, target):  # noqa: F811
    e = runtime
    e.mentor.generate(e.learner, e.aid)
    p = page_for(e, qtbot, qapp)
    with e.database.engine.begin() as c:
        table = "evaluation_results" if target == "evaluation" else "mentor_feedback"
        c.exec_driver_sql(f"DROP TRIGGER {table}_no_update")
        column = "result_json" if target == "evaluation" else "feedback_json"
        c.exec_driver_sql(f"UPDATE {table} SET {column}='{{}}'")
    p.refresh()
    assert "цілісність" in (p.detail.text() + p.feedback.text())
    if target == "evaluation":
        assert "%" not in p.detail.text() and "Помилка" in p.list.item(0).text()
    else:
        assert "100.00%" in p.detail.text()
    assert not p.evaluate_button.isEnabled() and not p.feedback_button.isEnabled()


def test_shell_results_compact_navigation_and_logout(learner_window, qtbot):  # noqa: F811
    from cyberforge.ui.navigation import View
    from tests.ui.test_learner_simulation import begin, click, confirm, open_main

    w = learner_window
    sim = begin(w, qtbot)
    open_main(sim, qtbot)
    click(qtbot, sim.decline)
    confirm(sim, qtbot)
    aid = sim.controller.attempt.attempt_id
    w.navigate(View.MY_RESULTS)
    p = w.learner_history
    click(qtbot, p.evaluate_button)
    qtbot.waitUntil(lambda: not p.running, timeout=10000)
    assert "%" in p.detail.text()
    for width, height in ((1100, 720), (900, 650)):
        w.resize(width, height)
        qtbot.wait(50)
        for b in (p.refresh_button, p.evaluate_button, p.feedback_button):
            assert b.geometry().right() < p.width()
    result = w.evaluations.read(w._token, aid)
    w.navigate(View.HOME)
    w.navigate(View.MY_RESULTS)
    assert w.evaluations.read(w._token, aid) == result
    w._signed_out()
    assert p.list.count() == 0 and not p.detail.text() and not p.feedback.text()


def test_close_waits_for_feedback_and_discards_revoked_session(
    learner_window,  # noqa: F811
    qtbot,
    monkeypatch,  # noqa: F811
):
    from threading import Event

    from cyberforge.ui.navigation import View
    from tests.ui.test_learner_simulation import begin, click, confirm, open_main

    w = learner_window
    sim = begin(w, qtbot)
    open_main(sim, qtbot)
    click(qtbot, sim.decline)
    confirm(sim, qtbot)
    aid = sim.controller.attempt.attempt_id
    w.evaluations.evaluate(w._token, aid)
    w.navigate(View.MY_RESULTS)
    entered, release = Event(), Event()
    original = w.mentor_feedback.generate

    def delayed(*args):
        entered.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(w.mentor_feedback, "generate", delayed)
    try:
        click(qtbot, w.learner_history.feedback_button)
        qtbot.waitUntil(entered.is_set)
        assert w.learner_history.running
        w.close()
        assert w._closing_pending and w._token is None
        assert w.isVisible()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not w.isVisible(), timeout=10000)
    assert not w.learner_history.running
    assert not w.learner_history.detail.text() and not w.learner_history.feedback.text()
    with w.accounts.database.engine.connect() as c:
        assert (
            c.exec_driver_sql("SELECT count(*) FROM evaluation_results").scalar_one()
            == 1
        )
        assert (
            c.exec_driver_sql("SELECT count(*) FROM mentor_feedback").scalar_one() == 0
        )


def test_malformed_history_source_clears_cached_ui(runtime, qtbot, qapp):  # noqa: F811
    e = runtime
    e.ev.evaluate(e.learner, e.aid)
    p = page_for(e, qtbot, qapp)
    assert p.list.count() == 1
    with e.database.engine.begin() as c:
        c.exec_driver_sql("DROP TRIGGER attempt_identity")
        c.exec_driver_sql(
            "UPDATE scenario_attempts SET scenario_name='' WHERE id=?", (str(e.aid),)
        )
    p.refresh()
    assert p.list.count() == 0 and not p.detail.text() and not p.feedback.text()
    assert "цілісність" in p.notice.text()


@pytest.mark.parametrize("revoke", ["logout", "deactivate"])
def test_heartbeat_preserves_results_selection_and_read_count(
    learner_window,  # noqa: F811
    qtbot,
    monkeypatch,
    revoke,  # noqa: F811
):  # noqa: F811
    from sqlalchemy import event

    from cyberforge.ui.navigation import View

    w = learner_window
    calls = []
    original = w.evaluations.history
    monkeypatch.setattr(
        w.evaluations,
        "history",
        lambda token: (calls.append(token), original(token))[1],
    )
    a = start(w.test_env)
    act(w.test_env, a, "system", "abandoned")
    start(w.test_env)
    w.navigate(View.MY_RESULTS)
    assert len(calls) == 1 and w.learner_history.list.count() == 2
    p = w.learner_history
    p.list.setCurrentRow(1)
    selected = p._selected_id()
    item = p.list.item(1)
    statements = []

    def trace(conn, cursor, sql, params, context, many):
        statements.append(sql)

    event.listen(w.accounts.database.engine, "before_cursor_execute", trace)
    try:
        for _ in range(3):
            w._sync_session()
            w._render()
    finally:
        event.remove(w.accounts.database.engine, "before_cursor_execute", trace)
    assert len(calls) == 1 and p.list.item(1) is item and p._selected_id() == selected
    assert not any(
        "FROM evaluation_results" in sql
        or sql.startswith(("INSERT", "UPDATE", "DELETE"))
        for sql in statements
    )
    p.list.setFocus()
    qtbot.keyClick(p.list, Qt.Key.Key_Up)
    assert p.list.currentRow() == 0
    # Locate the active attempt regardless of UUID ordering at equal timestamps.
    current = next(
        a
        for a in w.test_env.attempts.history(w.test_env.learner)
        if a.status == "IN_PROGRESS"
    )
    act(w.test_env, current, "system", "abandoned")
    start(w.test_env)
    p.refresh_button.click()
    assert p.list.count() == 3
    assert len(calls) == 2
    w.navigate(View.HOME)
    w.navigate(View.MY_RESULTS)
    assert len(calls) == 3
    if revoke == "logout":
        w.accounts.logout(w._token)
    else:
        from sqlalchemy import text

        with w.accounts.transaction(write=True) as db:
            db.execute(text("UPDATE users SET active=0 WHERE username='learner'"))
    w._sync_session()
    assert p.list.count() == 0 and not p.detail.text()


@pytest.mark.parametrize(
    "code", ["STORAGE_BUSY", "STORAGE_UNAVAILABLE", "ACCESS_DENIED"]
)
def test_feedback_operational_error_preserves_verified_score(
    runtime,  # noqa: F811
    qtbot,
    qapp,
    monkeypatch,
    code,  # noqa: F811
):  # noqa: F811
    from cyberforge.application.evaluations import EvaluationFailure

    e = runtime
    e.ev.evaluate(e.learner, e.aid)
    p = page_for(e, qtbot, qapp)
    original = p.mentor.read

    def failed(*args):
        raise EvaluationFailure(code, operation="feedback")

    monkeypatch.setattr(p.mentor, "read", failed)
    p.details(0)
    if code == "ACCESS_DENIED":
        assert p.list.count() == 0 and not p.detail.text() and not p.feedback.text()
        return
    assert "100.00%" in p.detail.text()
    assert "База даних" in p.feedback.text()
    monkeypatch.setattr(p.mentor, "read", original)
    e.mentor.generate(e.learner, e.aid)
    p.refresh_button.click()
    assert "100.00%" in p.detail.text() and "Навчальне пояснення" in p.feedback.text()
