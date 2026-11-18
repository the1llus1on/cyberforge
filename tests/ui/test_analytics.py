"""Analytics through the normal MainWindow and real worker lifecycle."""

import json
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import QFileDialog

from cyberforge.ui.navigation import View
from cyberforge.ui.shell import MainWindow
from cyberforge.ui.theme import apply_theme
from tests.test_analytics import add_learner, change_groups, complete, setup_services
from tests.test_scenario_integration import publication_env, publish  # noqa: F401

LEFT = Qt.MouseButton.LeftButton


@pytest.fixture
def analytics_window(qtbot, qapp, publication_env):  # noqa: F811
    env = publication_env
    publication = publish(env)
    second, _ = add_learner(env, "new_participant", "Новий учень")
    change_groups(
        env,
        env.group,
        instructors=(env.teacher_id,),
        learners=(env.learner_id, second.id),
    )
    evaluations, _, _ = setup_services(env)
    attempt = complete(
        evaluations, env.tokens["learner"], env.scenario.id, inspect=True
    )
    evaluations.evaluate(env.tokens["learner"], attempt.attempt_id)
    window = MainWindow(env.accounts, env.emails, env.webs)
    qtbot.addWidget(window)
    if not qapp.styleSheet():
        apply_theme(qapp)
    window.show()
    window.resize(1100, 720)
    window._authenticated(env.token)
    return env, window, publication


def open_analytics(qtbot, window):
    qtbot.mouseClick(window.nav_buttons[View.ANALYTICS], LEFT)
    window.scenario_list.setCurrentRow(0)
    qtbot.waitUntil(lambda: window.analytics_page.snapshot is not None, timeout=8000)
    return window.analytics_page


def test_dashboard_charts_filters_details_and_heartbeat(
    qtbot, analytics_window, monkeypatch
):
    env, window, publication = analytics_window
    page = open_analytics(qtbot, window)
    assert window.selected_scenario_id == env.scenario.id
    assert not window.new_scenario_button.isVisible()
    assert page.model.rowCount() == 2
    assert [c.format() for c in page.score_chart.bars][-1] == "[80,100] · 1 із 1"
    assert page.lifecycle_chart.bars[2].format() == "Завершені · 1 із 1"
    assert page.criterion_chart.selector.count() == 3
    assert page.criterion_chart.chart.bars[0].format() == "Виконано · 1 із 1"
    assert "100.00%" in page.cards[2].text()
    assert page.advice.text()

    calls = []
    original = page.service.load

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(page.service, "load", counted)
    window._sync_session()
    window._sync_session()
    qtbot.waitUntil(lambda: not page.check_pending)
    assert not calls

    page.versions.setCurrentIndex(page.versions.findData(publication.id))
    page.groups.setCurrentIndex(page.groups.findData(env.group.id))
    page.direction.setCurrentIndex(1)
    page.search.setText(" LEARNER ")
    qtbot.waitUntil(lambda: page.snapshot is not None and page.model.rowCount() == 1)
    assert page.snapshot.query.publication_id == publication.id
    assert page.snapshot.query.group_id == env.group.id
    assert page.snapshot.query.direction == "desc"
    assert page.snapshot.query.search == "learner"
    assert page.snapshot.metrics.mean_score == 100

    page.table.setFocus()
    page.table.setCurrentIndex(page.model.index(0, 0))
    qtbot.keyClick(page.table, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: page.history is not None)
    assert "Не застосовується" in page.detail_text.text()
    assert "100.00%" in page.detail_text.text()
    assert "Пояснення відсутнє" in page.detail_text.text()

    future = datetime.now(UTC) + timedelta(days=1)
    page.from_time.setDateTime(
        QDateTime.fromMSecsSinceEpoch(int(future.timestamp() * 1000))
    )
    page.from_enabled.setChecked(True)
    qtbot.waitUntil(
        lambda: page.snapshot is not None
        and page.snapshot.query.started_from is not None
    )
    assert page.snapshot.metrics.lifecycle.total == 0
    assert page.snapshot.metrics.current_learners == 1
    assert page.score_chart.empty.isVisible() and page.lifecycle_chart.empty.isVisible()
    assert page.history is None
    viewport = window.containers[View.ANALYTICS].viewport()
    assert page.width() <= viewport.width()
    assert page.exports[0].width() > 0
    window.navigate(View.CONSTRUCTOR)
    assert window.selected_scenario_id == env.scenario.id
    assert page.snapshot is None and page.model.rowCount() == 0


@pytest.mark.parametrize(
    "change", ["logout", "account_switch", "group", "navigation", "filter", "close"]
)
def test_worker_generation_and_revocation(qtbot, analytics_window, monkeypatch, change):
    env, window, _ = analytics_window
    page = open_analytics(qtbot, window)
    started, release = Event(), Event()
    original = page.service.load

    def delayed(*args):
        started.set()
        assert release.wait(8)
        return original(*args)

    monkeypatch.setattr(page.service, "load", delayed)
    page.refresh()
    qtbot.waitUntil(started.is_set)
    try:
        if change == "logout":
            env.accounts.logout(window._token)
            window._sync_session()
        elif change == "account_switch":
            window._authenticated(env.tokens["learner"])
            assert not window.nav_buttons[View.ANALYTICS].isVisible()
        elif change == "group":
            change_groups(env, env.group, learners=(env.learner_id,))
        elif change == "navigation":
            window.navigate(View.HOME)
        elif change == "filter":
            page.search.setText("відсутній")
        else:
            window.close()
        assert not page.model.rowCount()
    finally:
        release.set()
    if change == "group":
        qtbot.waitUntil(
            lambda: page.snapshot is not None and page.snapshot.total_learners == 0
        )
    elif change == "filter":
        qtbot.waitUntil(
            lambda: page.snapshot is not None
            and page.snapshot.query.search == "відсутній"
        )
        assert page.model.rowCount() == 0
    else:
        qtbot.waitUntil(lambda: not page.running)
        assert page.snapshot is None and page.model.rowCount() == 0
    if change == "close":
        qtbot.waitUntil(lambda: not window.isVisible())


def test_heartbeat_clears_published_scope_on_group_loss(qtbot, analytics_window):
    env, window, _ = analytics_window
    page = open_analytics(qtbot, window)
    assert page.model.rowCount() == 2
    change_groups(env, env.group, learners=(env.learner_id,))
    window._sync_session()
    qtbot.waitUntil(lambda: page.snapshot is None)
    assert page.model.rowCount() == 0 and not page.advice.text()
    assert page.criterion_chart.selector.count() == 0


def test_dashboard_export_through_save_dialog(
    qtbot, analytics_window, tmp_path, monkeypatch
):
    env, window, publication = analytics_window
    window._authenticated(env.tokens["admin"])
    page = open_analytics(qtbot, window)
    target = tmp_path / "analytics.json"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args: (str(target), "JSON")
    )
    qtbot.mouseClick(page.exports[1], LEFT)
    qtbot.waitUntil(lambda: target.exists() and not page.exporting)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["manifest"]["publications"] == [publication.id]
    assert payload["manifest"]["row_count"] == 2
    assert page.message.text() == "Файл збережено."
