"""Production integrity, authorization, concurrency and real migration guards."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import event, insert, text
from sqlalchemy.exc import IntegrityError

from cyberforge.application.evaluations import (
    EvaluationFailure,
    EvaluationService,
    criterion_columns,
    result_columns,
)
from cyberforge.application.learner_attempts import LearnerAttemptService
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.evaluation.canonical import canonical_bytes
from cyberforge.llm.factory import create_gateway
from cyberforge.persistence.database import Database
from cyberforge.persistence.models import (
    EvaluationCriterionRecord,
    EvaluationResultRecord,
)
from tests.test_evaluation import bundle, frozen  # noqa: F401
from tests.test_scenario_integration import publication_env  # noqa: F401


@pytest.fixture
def runtime(publication_env, monkeypatch):  # noqa: F811
    b = bundle.__wrapped__(SimpleNamespace(param="safe"), publication_env, monkeypatch)
    e = publication_env
    e.ev = EvaluationService(LearnerAttemptService(e.access))
    e.mentor = MentorFeedbackService(e.ev, create_gateway())
    e.aid = b[1].attempt.attempt_id
    e.evidence, e.expected = b[1], b[2]
    e.learner = e.tokens["learner"]
    return e


def counts(e):
    with e.database.engine.connect() as c:
        assert not c.exec_driver_sql("PRAGMA foreign_key_check").all()
        return tuple(
            c.exec_driver_sql("SELECT count(*) FROM " + t).scalar_one()
            for t in ("evaluation_results", "evaluation_criteria", "mentor_feedback")
        )


def test_concurrent_winner_and_feedback(runtime):
    e = runtime
    barrier = Barrier(2)

    def call(_):
        barrier.wait()
        return e.mentor.generate(e.learner, e.aid)

    with ThreadPoolExecutor(2) as pool:
        values = list(pool.map(call, range(2)))
    assert values[0] == values[1]
    assert counts(e) == (1, 8, 1)


@pytest.mark.parametrize("stage", ["detail", "parent", "commit"])
def test_write_failure_recovery(runtime, stage):
    e = runtime

    def fail(conn, cursor, statement, parameters, context, many):
        if (
            stage == "detail"
            and statement.startswith("INSERT INTO evaluation_criteria")
        ) or (
            stage == "parent" and statement.startswith("INSERT INTO evaluation_results")
        ):
            raise RuntimeError("injected failure")

    def commit_fail(conn):
        if stage == "commit":
            raise RuntimeError("injected commit failure")

    event.listen(e.database.engine, "after_cursor_execute", fail)
    event.listen(e.database.engine, "commit", commit_fail)
    try:
        with pytest.raises(RuntimeError):
            e.ev.evaluate(e.learner, e.aid)
    finally:
        event.remove(e.database.engine, "after_cursor_execute", fail)
        event.remove(e.database.engine, "commit", commit_fail)
    assert counts(e) == (0, 0, 0)
    assert e.ev.attempts.get(e.learner, e.aid) == e.evidence.attempt
    assert e.ev.attempts.events(e.learner, e.aid) == e.evidence.events
    assert e.ev.evaluate(e.learner, e.aid).criteria == e.expected.criteria


@pytest.mark.parametrize(
    "kind",
    [
        "parent_first",
        "missing",
        "extra",
        "duplicate",
        "position",
        "envelope",
        "source",
        "orphan",
    ],
)
def test_real_schema_invalid_seal(runtime, kind):
    e = runtime
    result = e.expected
    fields = result_columns(result, e.evidence)
    details = [criterion_columns(result.result_id, c) for c in result.criteria]
    if kind == "missing":
        details.pop()
    if kind == "extra":
        extra = dict(details[0], criterion_id="unknown", position=8)
        details.append(extra)
    if kind == "duplicate":
        details.append(details[0])
    if kind == "position":
        details[0]["position"] = 7
    if kind == "envelope":
        fields["weighted_numerator"] = "99"
    if kind == "source":
        fields["publication_id"] = 99999
    with pytest.raises(IntegrityError), e.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        if kind == "parent_first":
            db.execute(insert(EvaluationResultRecord).values(**fields))
        for d in details:
            db.execute(insert(EvaluationCriterionRecord).values(**d))
        if kind != "orphan":
            db.execute(insert(EvaluationResultRecord).values(**fields))
    assert counts(e) == (0, 0, 0)
    e.ev.evaluate(e.learner, e.aid)


@pytest.mark.parametrize("recursive", [0, 1])
@pytest.mark.parametrize(
    "table", ["evaluation_results", "evaluation_criteria", "mentor_feedback"]
)
@pytest.mark.parametrize("op", ["UPDATE", "DELETE", "REPLACE", "UPSERT"])
def test_actual_immutable_guards(runtime, recursive, table, op):
    e = runtime
    e.mentor.generate(e.learner, e.aid)
    with e.database.engine.connect() as c:
        c.exec_driver_sql(f"PRAGMA recursive_triggers={recursive}")
        columns = [r[1] for r in c.exec_driver_sql(f"PRAGMA table_info({table})")]
        names = ",".join(columns)
        values = c.exec_driver_sql(f"SELECT {names} FROM {table} LIMIT 1").one()
        if op == "UPDATE":
            sql, params = f"UPDATE {table} SET {columns[-1]}={columns[-1]}", ()
        elif op == "DELETE":
            sql, params = f"DELETE FROM {table}", ()
        else:
            insert_mode = "OR REPLACE " if op == "REPLACE" else ""
            placeholders = ",".join("?" for _ in columns)
            sql = f"INSERT {insert_mode}INTO {table} ({names}) VALUES ({placeholders})"
            if op == "UPSERT":
                sql += (
                    f" ON CONFLICT DO UPDATE SET {columns[-1]}=excluded.{columns[-1]}"
                )
            params = tuple(values)
        with pytest.raises(IntegrityError):
            c.exec_driver_sql(sql, params)
        c.rollback()
    assert counts(e) == (1, 8, 1)


@pytest.mark.parametrize(
    "mutation",
    [
        "result_json",
        "result_digest",
        "projection",
        "evidence",
        "missing_detail",
        "detail_score",
        "detail_weight",
        "detail_json",
        "result_source",
        "result_time",
        "recomputed_digest",
        "source_rubric",
        "event",
        "attempt",
    ],
)
def test_corruption_fails_closed_every_consumer(runtime, mutation):
    # Controlled tampering in an isolated DB simulates storage corruption.
    e = runtime
    original = e.ev.evaluate(e.learner, e.aid)
    with e.database.engine.begin() as c:
        c.exec_driver_sql("BEGIN IMMEDIATE")
        triggers = (
            c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'")
            .scalars()
            .all()
        )
        for name in triggers:
            c.exec_driver_sql(f'DROP TRIGGER "{name}"')
        sql = {
            "result_json": "UPDATE evaluation_results SET result_json='{}'",
            "result_digest": "UPDATE evaluation_results SET result_digest='bad'",
            "projection": "UPDATE evaluation_results SET weighted_numerator='0'",
            "evidence": "UPDATE evaluation_results SET evidence_json='{}'",
            "missing_detail": "DELETE FROM evaluation_criteria WHERE position=0",
            "detail_score": (
                "UPDATE evaluation_criteria SET weight='2' WHERE position=0"
            ),
            "detail_weight": (
                "UPDATE evaluation_criteria SET weight='0.1' WHERE position=0"
            ),
            "detail_json": (
                "UPDATE evaluation_criteria SET criterion_json='{}' WHERE position=0"
            ),
            "result_source": "UPDATE evaluation_results SET rubric_id='wrong'",
            "result_time": (
                "UPDATE evaluation_results SET "
                "evaluated_at='2020-01-01T00:00:00.000000Z'"
            ),
            "source_rubric": "UPDATE rubric_definitions SET payload='{}'",
            "event": (
                "UPDATE attempt_events SET operation_digest='bad' WHERE sequence=2"
            ),
            "attempt": "UPDATE scenario_attempts SET decision='LEFT'",
        }.get(mutation)
        if mutation == "recomputed_digest":
            from cyberforge.evaluation.contracts import EvaluationResultV1
            from cyberforge.evaluation.scoring import sealed

            fields = {
                k: getattr(original, k)
                for k in type(original).model_fields
                if k != "result_digest"
            }
            fields["result_id"] = uuid4()
            forged = sealed(EvaluationResultV1, fields, "result_digest")
            c.execute(
                text("UPDATE evaluation_results SET result_json=:j,result_digest=:d"),
                dict(j=canonical_bytes(forged).decode(), d=forged.result_digest),
            )
        else:
            c.exec_driver_sql(sql)
    for call in (e.ev.read, e.ev.evaluate, e.mentor.read, e.mentor.generate):
        with pytest.raises(EvaluationFailure) as exc:
            call(e.learner, e.aid)
        assert exc.value.error.code == "STORED_EVALUATION_INTEGRITY_ERROR"
    history = e.ev.history(e.learner)
    assert history[0].error.code == "STORED_EVALUATION_INTEGRITY_ERROR"
    with e.database.engine.connect() as c:
        assert c.exec_driver_sql(
            "SELECT id FROM evaluation_results"
        ).scalar_one() == str(original.result_id)


@pytest.mark.parametrize(
    "who",
    [None, "teacher", "admin", "other", "foreign", "logout", "deactivated", "stale"],
)
def test_all_endpoints_authorize_before_protected_reads(runtime, who):
    from cyberforge.domain.accounts import Role

    e = runtime
    e.mentor.generate(e.learner, e.aid)
    token = e.tokens.get(who)
    if who == "foreign":
        e.accounts.create_user(
            e.tokens["admin"], "foreign", "Учень", Role.LEARNER, e.password
        )
        token = e.accounts.login("foreign", e.password)
    if who in {"logout", "deactivated", "stale"}:
        token = e.learner
        if who == "logout":
            e.accounts.logout(token)
        else:
            with e.accounts.transaction(write=True) as db:
                db.execute(
                    text(
                        "UPDATE users SET "
                        + (
                            "active=0"
                            if who == "deactivated"
                            else "auth_version=auth_version+1"
                        )
                        + " WHERE id=:id"
                    ),
                    dict(id=e.evidence.attempt.learner_id),
                )
    trace = []

    def traced(conn, cursor, statement, parameters, context, many):
        trace.append(statement)

    event.listen(e.database.engine, "before_cursor_execute", traced)
    for call in (e.ev.read, e.ev.evaluate, e.mentor.read, e.mentor.generate):
        with pytest.raises(EvaluationFailure) as exc:
            call(token, e.aid)
        assert exc.value.error.code == "ACCESS_DENIED"
        assert exc.value.error.attempt_id is None and exc.value.error.result_id is None
    event.remove(e.database.engine, "before_cursor_execute", traced)
    assert not any("FROM evaluation_results" in s for s in trace)
    assert all("BEGIN" in s for s in trace if s.startswith("BEGIN"))


def test_historical_after_revoke_archive_membership_and_restart(runtime):
    e = runtime
    e.publications.change_grant(
        e.token,
        e.evidence.source.publication_id,
        e.group.id,
        active=False,
        expected_revision=1,
    )
    original = e.service.get(e.token, e.scenario.id)
    e.service.archive(
        e.token,
        original.id,
        expected_version=original.version,
        expected_revision=original.revision,
        expected_archive_revision=original.archive_revision,
    )
    e.groups.save_group(
        e.tokens["admin"],
        e.group.name,
        group_id=e.group.id,
        instructors=(e.teacher_id,),
        learners=(),
    )
    result = e.ev.evaluate(e.learner, e.aid)
    e.mentor.generate(e.learner, e.aid)
    with pytest.raises(ApplicationError):
        e.ev.attempts.content(e.learner, e.aid)
    path = e.database.engine.url.database
    other = Database(__import__("pathlib").Path(path))
    try:
        from cyberforge.application.accounts import AccountService
        from cyberforge.application.email_materials import EmailMaterialService
        from cyberforge.application.scenario_integration import (
            ScenarioIntegrationService,
        )
        from cyberforge.application.scenario_publication import (
            PublicationAccessService,
            ScenarioPublicationService,
        )
        from cyberforge.application.scenario_readiness import ScenarioReadinessService
        from cyberforge.application.scenarios import ScenarioService
        from cyberforge.application.web_materials import WebMaterialService

        accounts = AccountService(other)
        token = accounts.login("learner", e.password)
        pub = ScenarioPublicationService(
            ScenarioReadinessService(
                ScenarioIntegrationService(
                    WebMaterialService(
                        EmailMaterialService(
                            ScenarioService(accounts), create_gateway()
                        )
                    )
                )
            )
        )
        fresh = EvaluationService(LearnerAttemptService(PublicationAccessService(pub)))
        assert fresh.read(token, e.aid) == result
        assert (
            MentorFeedbackService(fresh, create_gateway()).read(token, e.aid)
            is not None
        )
    finally:
        other.close()


def test_unsafe_multi_revision_downgrade_rollback(runtime):
    e = runtime
    e.ev.evaluate(e.learner, e.aid)
    with pytest.raises(RuntimeError), e.database.engine.begin() as c:
        cfg = e.database.migration_config()
        cfg.attributes["connection"] = c
        command.downgrade(cfg, "0006_scenario_integration_publication")
    assert e.ev.read(e.learner, e.aid) is not None
    with e.database.engine.connect() as c:
        assert (
            c.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "0008_evaluations"
        )


def test_real_read_snapshot_authentication_and_next_request_revocation(
    runtime, monkeypatch
):
    e = runtime
    result = e.ev.evaluate(e.learner, e.aid)
    with e.database.engine.connect() as c:
        c.exec_driver_sql("PRAGMA journal_mode=WAL")  # Isolated test concurrency only.
    original = e.ev._sources
    trace = []

    def traced(conn, cursor, sql, params, context, many):
        trace.append(sql)

    event.listen(e.database.engine, "before_cursor_execute", traced)

    def sources(db, row):
        assert db.connection().connection.driver_connection.in_transaction
        with e.database.engine.begin() as writer:
            writer.exec_driver_sql("BEGIN IMMEDIATE")
            writer.exec_driver_sql(
                "UPDATE users SET active=0 WHERE id=?", (row.learner_id,)
            )
        return original(db, row)

    monkeypatch.setattr(e.ev, "_sources", sources)
    assert e.ev.read(e.learner, e.aid) == result
    event.remove(e.database.engine, "before_cursor_execute", traced)
    assert trace[0] == "BEGIN"
    assert next(i for i, s in enumerate(trace) if "FROM users" in s) < next(
        i for i, s in enumerate(trace) if "FROM evaluation_results" in s
    )
    with pytest.raises(EvaluationFailure) as exc:
        e.ev.read(e.learner, e.aid)
    assert exc.value.error.code == "ACCESS_DENIED"


def test_busy_and_storage_failure_are_operational_errors(runtime):
    import sqlite3

    from sqlalchemy.exc import OperationalError

    e = runtime
    with e.database.engine.connect() as locker:
        locker.exec_driver_sql("BEGIN IMMEDIATE")
        # Apply a short timeout to the next pooled service connection.
        with e.database.engine.connect() as c:
            c.exec_driver_sql("PRAGMA busy_timeout=1")
        with pytest.raises(EvaluationFailure) as exc:
            e.ev.evaluate(e.learner, e.aid)
        assert exc.value.error.code == "STORAGE_BUSY" and exc.value.error.retryable
        locker.rollback()
    result = e.ev.evaluate(e.learner, e.aid)

    def fail(conn, cursor, sql, params, context, many):
        if "FROM scenario_publications" in sql:
            raise OperationalError(
                sql, params, sqlite3.OperationalError("unable to open database file")
            )

    event.listen(e.database.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(EvaluationFailure) as exc:
            e.ev.read(e.learner, e.aid)
        assert (
            exc.value.error.code == "STORAGE_UNAVAILABLE" and exc.value.error.retryable
        )
    finally:
        event.remove(e.database.engine, "before_cursor_execute", fail)
    assert e.ev.read(e.learner, e.aid) == result


def test_malformed_attempt_metadata_history_fails_closed(runtime):
    e = runtime
    original = e.ev.evaluate(e.learner, e.aid)
    with e.database.engine.begin() as c:
        c.exec_driver_sql("DROP TRIGGER attempt_identity")
        c.exec_driver_sql(
            "UPDATE scenario_attempts SET scenario_name='' WHERE id=?", (str(e.aid),)
        )
    with pytest.raises(EvaluationFailure) as exc:
        e.ev.read(e.learner, e.aid)
    assert exc.value.error.code == "STORED_EVALUATION_INTEGRITY_ERROR"
    with pytest.raises(EvaluationFailure) as exc:
        e.ev.history(e.learner)
    assert exc.value.error.code == "IMMUTABLE_SOURCE_INTEGRITY_ERROR"
    with e.database.engine.connect() as c:
        assert c.exec_driver_sql(
            "SELECT id FROM evaluation_results"
        ).scalar_one() == str(original.result_id)
