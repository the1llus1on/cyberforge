"""Phase 11 integration against the accepted 0008 schema and offline services."""

import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cyberforge.analytics.contracts import (
    AnalyticsExportManifestV1,
    AnalyticsQueryV1,
    HistoryQueryV1,
    LearnerAnalyticsRowV1,
    Ratio,
    display_percent,
)
from cyberforge.application.analytics import (
    AnalyticsStorageError,
    ScenarioAnalyticsService,
)
from cyberforge.application.evaluations import EvaluationService
from cyberforge.application.learner_attempts import (
    AttemptEventService,
    LearnerAttemptService,
)
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from tests.test_evaluation import BASE, bundle, frozen  # noqa: F401
from tests.test_scenario_integration import publication_env, publish  # noqa: F401


def setup_services(env):
    ev = EvaluationService(LearnerAttemptService(env.access))
    return (
        ev,
        ScenarioAnalyticsService(ev),
        AnalyticsQueryV1(scenario_id=env.scenario.id),
    )


def complete(ev, token, scenario, *, inspect=False, web=False, leave=False):
    attempt = ev.attempts.start_or_resume(token, scenario)
    events = AttemptEventService(ev.attempts)

    def record(surface=None, action=None, *, display=False, control=None, **command):
        nonlocal attempt
        kwargs = dict(request_id=uuid4(), expected_revision=attempt.revision)
        if display:
            attempt = events._display_acknowledger(token, attempt.attempt_id)(**kwargs)
        elif control is not None:
            attempt = events.browser_control(
                token, attempt.attempt_id, control=control, **kwargs
            )
        else:
            attempt = events.record(
                token,
                attempt.attempt_id,
                surface=surface,
                action_id=action,
                **kwargs,
                **command,
            )

    record("email", "email_opened")
    if inspect:
        record("email", "inspect_sender")
    if web:
        _, state = ev.attempts.content(token, attempt.attempt_id)
        record(
            "transition",
            "open_internal",
            navigation=ev.attempts.access.resolve_internal(
                token, attempt.publication_id
            ),
            source_message_identifier=state.link.source_message_identifier,
        )
        record(display=True)
        if leave:
            record(control="leave")
    else:
        record("transition", "decline")
    record("system", "completed")
    return attempt


def add_learner(env, login, display_name):
    account = env.accounts.create_user(
        env.tokens["admin"], login, display_name, Role.LEARNER, env.password
    )
    return account, env.accounts.login(login, env.password)


def change_groups(env, group, *, instructors=(), learners=()):
    return env.groups.save_group(
        env.tokens["admin"],
        group.name,
        group_id=group.id,
        instructors=instructors,
        learners=learners,
    )


def archive_state(env, scenario_id, *, archive):
    current = env.service.get(env.token, scenario_id)
    operation = env.service.archive if archive else env.service.restore
    return operation(
        env.token,
        scenario_id,
        expected_version=current.version,
        expected_revision=current.revision,
        expected_archive_revision=current.archive_revision,
    )


def table_state(env):
    with env.database.engine.connect() as connection:
        return tuple(
            tuple(connection.exec_driver_sql(f"SELECT * FROM {name}").all())
            for name in (
                "scenarios",
                "scenario_publications",
                "publication_groups",
                "scenario_attempts",
                "attempt_events",
                "evaluation_results",
                "evaluation_criteria",
                "mentor_feedback",
            )
        )


def test_contract_boundaries():
    first = datetime(2026, 11, 18, 2, tzinfo=UTC)
    query = AnalyticsQueryV1(scenario_id=1, started_from=first, search="  СПРОБА   ")
    assert query.search == "спроба" and query.started_from == first
    for values in (
        dict(scenario_id=True),
        dict(schema_version="v2"),
        dict(group_id=0),
        dict(page_size=101),
        dict(page=0),
        dict(sort="sql"),
        dict(started_from=first.replace(tzinfo=None)),
        dict(started_from=first, started_to=first),
        dict(search="x" * 161),
        dict(token="secret"),
    ):
        with pytest.raises(ValidationError):
            AnalyticsQueryV1.model_validate({"scenario_id": 1, **values})
    with pytest.raises(ValidationError):
        HistoryQueryV1(learner_id=1, result_id=uuid4())
    with pytest.raises(ValidationError):
        Ratio(numerator=1, denominator=0)
    assert display_percent(Decimal("50.125")) == "50.12"
    assert display_percent(Decimal("50.135")) == "50.14"
    assert Ratio(numerator=0, denominator=0).percent is None


def test_role_scope_history_and_idor(publication_env):  # noqa: F811
    e = publication_env
    pub = publish(e)
    ev, service, query = setup_services(e)
    attempt = complete(ev, e.tokens["learner"], e.scenario.id)
    result = ev.evaluate(e.tokens["learner"], attempt.attempt_id)
    args = HistoryQueryV1(
        learner_id=e.learner_id,
        attempt_id=attempt.attempt_id,
        result_id=result.result_id,
    )
    for token in (None, "expired", e.tokens["learner"], e.tokens["other"]):
        with pytest.raises(AccessDenied):
            service.summary(token, query)
        with pytest.raises(AccessDenied):
            service.history(token, query, args)
        with pytest.raises(AccessDenied):
            service.recommendations(token, query)
    assert (
        service.history(e.token, query, args).attempts[0].result_id == result.result_id
    )
    assert service.summary(e.tokens["admin"], query).rows[0].learner_id == e.learner_id
    for override in (
        dict(group_id=e.other_group.id),
        dict(group_id=987),
        dict(scenario_id=987),
        dict(publication_id=987),
    ):
        with pytest.raises(AccessDenied):
            service.summary(e.token, query.model_copy(update=override))
    other_scenario = e.service.create(
        e.tokens["other"], {"topic": "Інший сценарій", "difficulty": "beginner"}
    )
    with pytest.raises(AccessDenied):
        service.summary(
            e.token, query.model_copy(update={"scenario_id": other_scenario.id})
        )
    for override in (
        dict(learner_id=987),
        dict(attempt_id=uuid4()),
        dict(result_id=uuid4()),
    ):
        with pytest.raises(AccessDenied):
            service.history(e.token, query, args.model_copy(update=override))

    e.group = change_groups(e, e.group, instructors=(e.teacher_id,))
    snapshot = service.summary(e.token, query)
    assert snapshot.metrics.current_learners == 0
    assert snapshot.rows[0].historical and not snapshot.rows[0].current
    e.publications.change_grant(
        e.token, pub.id, e.group.id, active=False, expected_revision=1
    )
    archived = archive_state(e, e.scenario.id, archive=True)
    assert service.summary(e.token, query).scope.status == "archived"
    assert service.history(e.token, query, args).total == 1
    archive_state(e, archived.id, archive=False)
    e.group = change_groups(e, e.group)
    assert service.summary(e.token, query).total_learners == 0
    with pytest.raises(AccessDenied):
        service.history(e.token, query, args)
    assert service.history(e.tokens["admin"], query, args).total == 1


def test_metrics_tie_break_zero_pending_and_mixed_cohort(publication_env):  # noqa: F811
    e = publication_env
    publish(e)
    ev, service, query = setup_services(e)
    second, second_token = add_learner(e, "second", "Другий")
    current_only, _ = add_learner(e, "third", "Третій")
    e.group = change_groups(
        e,
        e.group,
        instructors=(e.teacher_id,),
        learners=(e.learner_id, second.id, current_only.id),
    )
    # Existing frozen clock makes all completion timestamps equal.
    a = complete(ev, e.tokens["learner"], e.scenario.id)
    b = complete(ev, e.tokens["learner"], e.scenario.id, inspect=True)
    c = complete(ev, second_token, e.scenario.id, web=True, leave=True)
    ev.evaluate(e.tokens["learner"], b.attempt_id)
    ev.evaluate(second_token, c.attempt_id)
    assert a.attempt_id < b.attempt_id
    latest = service.summary(e.token, query)
    assert latest.metrics.mean_score == Decimal("0.00")
    assert latest.metrics.web_transition == Ratio(numerator=1, denominator=1)
    assert latest.metrics.score_distribution == (1, 0, 0, 0, 0)
    assert latest.metrics.current_learners == 3
    assert latest.quality.selected.pending == 1
    assert latest.quality.filtered.scored_nonzero == 1
    assert latest.quality.filtered.scored_zero == 1
    assert latest.metrics.lifecycle.completed == 3
    indexed = {row.learner_id: row for row in latest.rows}
    assert indexed[e.learner_id].result_status == "COMPLETED_PENDING_EVALUATION"
    assert indexed[current_only.id].activity == "NOT_STARTED"
    all_results = service.summary(
        e.token, query.model_copy(update={"aggregation": "ALL_COMPLETED_ATTEMPTS"})
    )
    assert all_results.metrics.mean_score == Decimal("50.00")
    assert all_results.metrics.web_transition == Ratio(numerator=1, denominator=2)
    assert all_results.metrics.scored_coverage == Ratio(numerator=2, denominator=3)
    assert all_results.metrics.score_distribution == (1, 0, 0, 0, 1)
    assert next(
        row for row in all_results.rows if row.learner_id == e.learner_id
    ).web_not_applicable
    safe = next(
        c
        for c in all_results.criteria
        if c.key.criterion_id == "transition.safe_decline"
    )
    assert safe.met_rate == Ratio(numerator=1, denominator=2)
    assert safe.not_met_rate == Ratio(numerator=1, denominator=2)
    assert (
        service.summary(
            e.token, query.model_copy(update={"started_to": BASE})
        ).metrics.current_learners
        == 3
    )
    assert (
        service.summary(
            e.token, query.model_copy(update={"started_to": BASE})
        ).metrics.lifecycle.total
        == 0
    )
    assert (
        service.summary(
            e.token, query.model_copy(update={"started_from": BASE})
        ).metrics.lifecycle.total
        == 3
    )
    assert (
        service.summary(
            e.token, query.model_copy(update={"search": " дРУГ "})
        ).total_learners
        == 1
    )


def test_accepted_results_remain_immutable(bundle, publication_env, monkeypatch):  # noqa: F811
    _, evidence, _, expected_feedback, _ = bundle
    env = publication_env
    from cyberforge.application.mentor_feedback import MentorFeedbackService
    from cyberforge.llm.factory import create_gateway

    ev, service, query = setup_services(env)
    token = env.tokens["learner"]
    result = ev.evaluate(token, evidence.attempt.attempt_id)
    MentorFeedbackService(ev, create_gateway()).generate(
        token, result.attempt.attempt_id
    )
    before = table_state(env)

    def rescore(*args, **kwargs):
        pytest.fail("analytics invoked scoring")

    monkeypatch.setattr(ev.scorer, "score", rescore)
    monkeypatch.setattr(ev.scorer, "evidence", rescore)
    first = service.summary(env.token, query)
    attempt = service.history(
        env.token, query, HistoryQueryV1(learner_id=env.learner_id)
    ).attempts[0]
    assert (
        attempt.score == result.score_percent and attempt.result_id == result.result_id
    )
    assert attempt.feedback_status == "VERIFIED"
    assert attempt.feedback[-1] == expected_feedback.explanation.limitations[-1]
    assert first.metrics.web_transition.numerator == int(result.attempt.web_visited)
    assert first.metrics.web_transition.denominator == 1
    assert first.metrics.observations.confirm == sum(
        o.action_id == "confirm" for o in result.critical_observations
    )
    assert first.metrics.observations.submit_synthetic == sum(
        o.action_id == "submit_synthetic" for o in result.critical_observations
    )
    assert first.metrics.observations.critical_count is None
    assert first.recommendations == service.recommendations(env.token, query)
    assert (first.metrics.mean_score is None) == (result.status == "UNSCORABLE")
    assert before == table_state(env)


@pytest.mark.parametrize(
    ("trigger", "statement", "expected"),
    [
        (
            "evaluation_results_no_update",
            "UPDATE evaluation_results SET result_digest = 'bad'",
            "STORED_EVALUATION_INTEGRITY_ERROR",
        ),
        (
            "evaluation_criteria_no_update",
            "UPDATE evaluation_criteria SET criterion_json = '{}'",
            "STORED_EVALUATION_INTEGRITY_ERROR",
        ),
        (
            "event_no_update",
            "UPDATE attempt_events SET operation_digest = 'bad' "
            "WHERE action_id = 'completed'",
            "STORED_EVALUATION_INTEGRITY_ERROR",
        ),
        (
            "attempt_identity",
            "UPDATE scenario_attempts SET completed_at = 'invalid'",
            "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
        ),
    ],
)
def test_corruption_excluded(publication_env, trigger, statement, expected):  # noqa: F811
    e = publication_env
    publish(e)
    ev, service, query = setup_services(e)
    attempt = complete(ev, e.tokens["learner"], e.scenario.id)
    ev.evaluate(e.tokens["learner"], attempt.attempt_id)
    with e.database.engine.begin() as connection:
        connection.exec_driver_sql(f"DROP TRIGGER {trigger}")
        connection.exec_driver_sql(statement)
    snapshot = service.summary(e.token, query)
    assert snapshot.metrics.mean_score is None
    assert snapshot.rows[0].result_status == expected
    assert snapshot.quality.selected.total == 1
    detail = service.history(
        e.token, query, HistoryQueryV1(learner_id=e.learner_id)
    ).attempts[0]
    assert detail.result_id is None and detail.score is None and not detail.criteria


@pytest.mark.parametrize("column", ("scenario_id", "learner_id", "publication_id"))
def test_corrupt_evaluation_projection_retains_attempt(
    publication_env,  # noqa: F811
    monkeypatch,
    column,
):
    from cyberforge.application import learner_attempts

    e = publication_env
    publication = publish(e)
    scenario = e.scenario
    ev, service, query = setup_services(e)
    earlier = complete(ev, e.tokens["learner"], scenario.id)
    earlier_result = ev.evaluate(e.tokens["learner"], earlier.attempt_id)
    assert earlier_result.score_percent == 50

    class LaterClock(datetime):
        @classmethod
        def now(cls, tz=None):
            stamp = BASE + timedelta(seconds=1)
            return stamp.astimezone(tz) if tz else stamp.replace(tzinfo=None)

    monkeypatch.setattr(learner_attempts, "datetime", LaterClock)
    latest = complete(ev, e.tokens["learner"], scenario.id, inspect=True)
    corrupt_result = ev.evaluate(e.tokens["learner"], latest.attempt_id)
    assert latest.completed_at > earlier.completed_at
    assert corrupt_result.score_percent == 100

    if column == "learner_id":
        other, _ = add_learner(e, "other_learner", "Інший учень")
        replacement = other.id
    else:
        e.scenario = e.service.create(
            e.token, {"topic": "Інший сценарій", "difficulty": "beginner"}
        )
        replacement = e.scenario.id if column == "scenario_id" else publish(e).id
    with e.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER evaluation_results_no_update")
        connection.exec_driver_sql(
            f"UPDATE evaluation_results SET {column} = ? WHERE id = ?",
            (replacement, str(corrupt_result.result_id)),
        )
        assert not connection.exec_driver_sql("PRAGMA foreign_key_check").all()
    before = table_state(e)
    state = "STORED_EVALUATION_INTEGRITY_ERROR"
    all_query = query.model_copy(update={"aggregation": "ALL_COMPLETED_ATTEMPTS"})
    exact = HistoryQueryV1(learner_id=e.learner_id, attempt_id=latest.attempt_id)
    for token in (e.token, e.tokens["admin"]):
        snapshot = service.summary(token, query)
        assert (
            snapshot.metrics.lifecycle.total
            == snapshot.metrics.lifecycle.completed
            == 2
        )
        assert snapshot.metrics.completing_learners == snapshot.total_learners == 1
        assert snapshot.metrics.mean_score is None
        assert snapshot.metrics.scored_coverage == Ratio(numerator=0, denominator=1)
        assert snapshot.quality.filtered.total == 2
        assert snapshot.quality.filtered.stored_integrity_error == 1
        assert snapshot.quality.filtered.scored_nonzero == 1
        assert snapshot.quality.selected.stored_integrity_error == 1
        assert snapshot.rows[0].result_status == state
        assert snapshot.rows[0].score is None

        all_results = service.summary(token, all_query)
        assert all_results.metrics.mean_score == 50
        assert all_results.metrics.scored_coverage == Ratio(numerator=1, denominator=2)
        assert all_results.quality.selected.stored_integrity_error == 1

        detail = service.history(token, query, exact).attempts[0]
        assert detail.result_status == state
        assert (detail.scenario_id, detail.learner_id, detail.publication.id) == (
            scenario.id,
            e.learner_id,
            publication.id,
        )
        assert detail.group.id == e.group.id
        assert detail.result_id is None and detail.score is None
        assert not (detail.criteria or detail.facts or detail.feedback)
        with pytest.raises(AccessDenied):
            service.history(
                token,
                query,
                exact.model_copy(update={"result_id": corrupt_result.result_id}),
            )
    assert before == table_state(e)


def test_ambiguous_evaluation_identity_remains_hidden(publication_env):  # noqa: F811
    e = publication_env
    publish(e)
    ev, service, query = setup_services(e)
    attempt = complete(ev, e.tokens["learner"], e.scenario.id)
    result = ev.evaluate(e.tokens["learner"], attempt.attempt_id)
    other, _ = add_learner(e, "other_learner", "Інший учень")
    with e.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER evaluation_results_no_update")
        connection.exec_driver_sql(
            "UPDATE evaluation_results "
            "SET learner_id = ?, result_json = '{}', evidence_json = '{}' WHERE id = ?",
            (other.id, str(result.result_id)),
        )
    exact = HistoryQueryV1(learner_id=e.learner_id, attempt_id=attempt.attempt_id)
    for token in (e.token, e.tokens["admin"]):
        assert service.summary(token, query).metrics.lifecycle.total == 0
        with pytest.raises(AccessDenied):
            service.history(token, query, exact)


def test_export_complete_private_and_revocable(publication_env, tmp_path, monkeypatch):  # noqa: F811
    from cyberforge.analytics import export

    e = publication_env
    publish(e)
    ev, service, query = setup_services(e)
    second, second_token = add_learner(e, "second", '  =Формула, "лапки"\nтест')
    e.group = change_groups(
        e, e.group, instructors=(e.teacher_id,), learners=(e.learner_id, second.id)
    )
    a = complete(ev, second_token, e.scenario.id, web=True, leave=True)
    ev.evaluate(second_token, a.attempt_id)
    query = query.model_copy(update={"page_size": 1})
    assert len(service.summary(e.token, query).rows) == 1
    before = table_state(e)
    j = tmp_path / "analytics.json"
    c = tmp_path / "analytics.csv"
    service.export(e.token, query, j, "json")
    service.export(e.token, query, c, "csv")
    value = json.loads(j.read_text(encoding="utf-8"))
    assert value["manifest"]["schema_version"] == "analytics-export-manifest-v1"
    manifest_value = AnalyticsExportManifestV1.model_validate(value["manifest"])
    assert manifest_value.row_count == 2
    assert manifest_value.scenario_id == e.scenario.id
    assert all(LearnerAnalyticsRowV1.model_validate(row) for row in value["rows"])
    with pytest.raises(ApplicationError, match="бази даних"):
        service.export(e.token, query, e.database.engine.url.database, "json")
    assert [row["score"] for row in value["rows"]] == ["0.00", None]
    assert [row["result_status"] for row in value["rows"]] == [
        "SCORED_ZERO",
        "NOT_STARTED",
    ]
    with c.open(encoding="utf-8", newline="") as source:
        manifest, first, second_row = list(csv.DictReader(source))
    assert json.loads(manifest["manifest"])["row_count"] == 2
    assert first["name"] == '\'=Формула, "лапки"\nтест'
    assert first["score"] == "0.00" and second_row["score"] == ""
    assert before == table_state(e)
    assert e.token not in j.read_text(encoding="utf-8")
    for invalid in (
        "+formula",
        "  -cmd",
        "\ttext",
        " \rtext",
        "\ntext",
        "\u200b@formula",
    ):
        assert export.safe_cell(invalid) == "'" + invalid

    original = export._write_json

    def revoke(*args):
        original(*args)
        e.accounts.logout(e.token)

    monkeypatch.setattr(export, "_write_json", revoke)
    denied = tmp_path / "denied.json"
    with pytest.raises(AccessDenied):
        service.export(e.token, query, denied, "json")
    assert not denied.exists() and not list(tmp_path.glob(".cyberforge-*.tmp"))
    with pytest.raises(AccessDenied):
        service.export(e.tokens["learner"], query, denied, "csv")
    assert not denied.exists()


@pytest.mark.parametrize(
    ("cause", "code"),
    [("database is locked", "STORAGE_BUSY"), ("disk I/O error", "STORAGE_UNAVAILABLE")],
)
def test_operational_error_is_unavailable(publication_env, cause, code):  # noqa: F811
    e = publication_env
    _, service, query = setup_services(e)
    from sqlalchemy import event

    def fail(connection, cursor, statement, *args):
        if statement == "BEGIN":
            import sqlite3

            from sqlalchemy.exc import OperationalError

            raise OperationalError(statement, (), sqlite3.OperationalError(cause))

    event.listen(e.database.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(AnalyticsStorageError) as exc:
            service.summary(e.token, query)
        assert exc.value.code == code
    finally:
        event.remove(e.database.engine, "before_cursor_execute", fail)


def test_multigroup_multiversion_and_filtered_history(publication_env):  # noqa: F811
    e = publication_env
    first_pub = publish(e)
    ev, service, query = setup_services(e)
    other = e.accounts.current(e.tokens["other"])
    second, second_token = add_learner(e, "second", "Другий учень")
    change_groups(
        e,
        e.other_group,
        instructors=(e.teacher_id, other.id),
        learners=(e.learner_id, second.id),
    )
    e.publications.change_grant(
        e.token, first_pub.id, e.other_group.id, active=True, expected_revision=0
    )
    a = complete(ev, e.tokens["learner"], e.scenario.id, inspect=True)
    ev.evaluate(e.tokens["learner"], a.attempt_id)
    assert a.authorization_group_id == e.group.id
    e.scenario = e.service.create_next_draft(
        e.token, e.service.get(e.token, e.scenario.id)
    )
    second_pub = publish(e)
    e.publications.change_grant(
        e.token, second_pub.id, e.other_group.id, active=True, expected_revision=0
    )
    b = complete(ev, e.tokens["learner"], e.scenario.id, web=True, leave=True)
    ev.evaluate(e.tokens["learner"], b.attempt_id)
    c = complete(ev, second_token, e.scenario.id, web=True, leave=True)
    ev.evaluate(second_token, c.attempt_id)
    d = ev.attempts.start_or_resume(second_token, e.scenario.id)
    AttemptEventService(ev.attempts).record(
        second_token,
        d.attempt_id,
        request_id=uuid4(),
        expected_revision=d.revision,
        surface="system",
        action_id="abandoned",
    )
    ev.attempts.start_or_resume(second_token, e.scenario.id)
    scoped = query.model_copy(update={"aggregation": "ALL_COMPLETED_ATTEMPTS"})
    snapshot = service.summary(e.token, scoped)
    assert snapshot.metrics.current_learners == snapshot.total_learners == 2
    assert snapshot.metrics.lifecycle.total == 5
    assert (
        snapshot.metrics.lifecycle.abandoned
        == snapshot.metrics.lifecycle.in_progress
        == 1
    )
    assert display_percent(snapshot.metrics.mean_score) == "33.33"
    assert snapshot.metrics.scored_versions == 2
    criterion = [s for s in snapshot.criteria if s.key.criterion_id == "email.sender"]
    assert [(s.key.publication_id, s.met, s.not_met) for s in criterion] == [
        (first_pub.id, 1, 0),
        (second_pub.id, 0, 2),
    ]
    assert "різні версії" in snapshot.recommendations[0]
    assert snapshot.rows[0].groups[0].id in {e.group.id, e.other_group.id}
    group_b = service.summary(
        e.token, scoped.model_copy(update={"group_id": e.other_group.id})
    )
    assert group_b.metrics.current_learners == 2
    assert group_b.metrics.lifecycle.completed == 1
    assert group_b.metrics.mean_score == 0
    with pytest.raises(AccessDenied):
        service.history(
            e.token,
            query.model_copy(update={"publication_id": first_pub.id}),
            HistoryQueryV1(learner_id=e.learner_id, attempt_id=b.attempt_id),
        )
    with pytest.raises(AccessDenied):
        service.history(
            e.token,
            query,
            HistoryQueryV1(learner_id=e.learner_id, attempt_id=c.attempt_id),
        )
    assert (
        service.history(
            e.token,
            query.model_copy(update={"status": "COMPLETED"}),
            HistoryQueryV1(learner_id=second.id),
        ).total
        == 1
    )


def test_corrupt_latest_preserves_coverage_and_earlier_history(publication_env):  # noqa: F811
    e = publication_env
    publish(e)
    ev, service, query = setup_services(e)
    # Equal timestamps and first UUID deterministically select the first result.
    first = complete(ev, e.tokens["learner"], e.scenario.id, inspect=True)
    second = complete(ev, e.tokens["learner"], e.scenario.id)
    for attempt in (first, second):
        ev.evaluate(e.tokens["learner"], attempt.attempt_id)
    with e.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER attempt_identity")
        connection.exec_driver_sql(
            "UPDATE scenario_attempts SET completed_at = 'invalid' WHERE id = ?",
            (str(first.attempt_id),),
        )
    latest = service.summary(e.token, query)
    assert latest.metrics.mean_score is None and latest.quality.ordering_errors == 1
    assert latest.quality.selected.source_integrity_error == 1
    assert latest.quality.filtered.scored_nonzero == 1
    all_results = service.summary(
        e.token, query.model_copy(update={"aggregation": "ALL_COMPLETED_ATTEMPTS"})
    )
    assert all_results.metrics.mean_score == 50


def test_feedback_corruption_keeps_verified_score(publication_env):  # noqa: F811
    from cyberforge.application.mentor_feedback import MentorFeedbackService
    from cyberforge.llm.factory import create_gateway

    e = publication_env
    publish(e)
    ev, service, query = setup_services(e)
    attempt = complete(ev, e.tokens["learner"], e.scenario.id, inspect=True)
    ev.evaluate(e.tokens["learner"], attempt.attempt_id)
    MentorFeedbackService(ev, create_gateway()).generate(
        e.tokens["learner"], attempt.attempt_id
    )
    with e.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER mentor_feedback_no_update")
        connection.exec_driver_sql("UPDATE mentor_feedback SET feedback_digest = 'bad'")
    snapshot = service.summary(e.token, query)
    assert snapshot.metrics.mean_score == 100
    assert snapshot.quality.selected.feedback_integrity_error == 1
    assert snapshot.quality.selected.scored_nonzero == 1
    detail = service.history(
        e.token, query, HistoryQueryV1(learner_id=e.learner_id)
    ).attempts[0]
    assert (
        detail.score == 100
        and detail.feedback_status == "STORED_FEEDBACK_INTEGRITY_ERROR"
    )
    assert not detail.feedback


def test_invalid_historical_group_is_never_disclosed(publication_env):  # noqa: F811
    e = publication_env
    pub = publish(e)
    ev, service, query = setup_services(e)
    other = e.accounts.current(e.tokens["other"])
    change_groups(
        e,
        e.other_group,
        instructors=(e.teacher_id, other.id),
        learners=(e.learner_id,),
    )
    e.publications.change_grant(
        e.token, pub.id, e.other_group.id, active=True, expected_revision=0
    )
    attempt = complete(ev, e.tokens["learner"], e.scenario.id)
    ev.evaluate(e.tokens["learner"], attempt.attempt_id)
    with e.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER attempt_identity")
        connection.exec_driver_sql("DROP TRIGGER attempt_event_state")
        connection.exec_driver_sql(
            "UPDATE scenario_attempts SET authorization_group_id = ?",
            (e.other_group.id,),
        )
    snapshot = service.summary(e.tokens["admin"], query)
    assert snapshot.metrics.lifecycle.total == 0
    assert all(not row.historical for row in snapshot.rows)
    with pytest.raises(AccessDenied):
        service.history(
            e.tokens["admin"],
            query,
            HistoryQueryV1(learner_id=e.learner_id, attempt_id=attempt.attempt_id),
        )
    # The instructor can access Group B, but cannot acquire Group A history
    # through the altered attempt row after losing the Group A assignment.
    change_groups(e, e.group, learners=(e.learner_id,))
    group_b = query.model_copy(update={"group_id": e.other_group.id})
    assert service.summary(e.token, group_b).metrics.lifecycle.total == 0
    with pytest.raises(AccessDenied):
        service.history(
            e.token,
            group_b,
            HistoryQueryV1(learner_id=e.learner_id, attempt_id=attempt.attempt_id),
        )


def test_revocation_during_consistent_snapshot(publication_env, monkeypatch, tmp_path):  # noqa: F811
    from cyberforge.application import analytics

    e = publication_env
    publish(e)
    ev, service, query = setup_services(e)
    attempt = complete(ev, e.tokens["learner"], e.scenario.id)
    ev.evaluate(e.tokens["learner"], attempt.attempt_id)
    with e.database.engine.connect() as connection:
        assert (
            connection.exec_driver_sql("PRAGMA journal_mode=WAL").scalar_one() == "wal"
        )
    aggregate = analytics.aggregate

    def revoke_during_read(*args):
        change_groups(e, e.group, learners=(e.learner_id,))
        original_snapshot = aggregate(*args)
        assert original_snapshot[0].scored_coverage.numerator == 1
        return original_snapshot

    monkeypatch.setattr(analytics, "aggregate", revoke_during_read)
    with pytest.raises(AccessDenied):
        service.summary(e.token, query)
    change_groups(e, e.group, instructors=(e.teacher_id,), learners=(e.learner_id,))
    target = tmp_path / "existing.csv"
    target.write_text("existing file", encoding="utf-8")
    with pytest.raises(AccessDenied):
        service.export(e.token, query, target, "csv")
    assert target.read_text(encoding="utf-8") == "existing file"
    assert not list(tmp_path.glob(".cyberforge-*.tmp"))
