"Scratch-only SQLAlchemy/SQLite protocol, NOT migration 0008 or ORM models."

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from cyberforge.domain.accounts import AccessDenied, Role
from cyberforge.scenario_integration.contracts import CRITERIA

SPEC = (
    {"criterion_id": "email.sender", "position": 0},
    {"criterion_id": "web.address", "position": 1},
)


@pytest.fixture
def proof(scenario_env):
    e = scenario_env
    e.trace = []
    event.listen(
        e.database.engine,
        "before_cursor_execute",
        lambda conn,
        cursor,
        statement,
        parameters,
        context,
        executemany: e.trace.append(statement),
    )
    with e.database.engine.begin() as c:
        c.exec_driver_sql("BEGIN IMMEDIATE")
        c.exec_driver_sql(
            "CREATE TABLE proof_attempts(id INTEGER PRIMARY "
            "KEY,learner_id INTEGER NOT NULL REFERENCES "
            "users(id),completed INTEGER NOT NULL,rubric TEXT NOT "
            "NULL)"
        )
        c.exec_driver_sql(
            "CREATE TABLE proof_registry(criterion_id TEXT PRIMARY KEY,"
            "ordinal INTEGER NOT NULL UNIQUE)"
        )
        for ordinal, spec in enumerate(CRITERIA):
            c.exec_driver_sql(
                "INSERT INTO proof_registry VALUES (?,?)", (spec.id, ordinal)
            )
        owner = e.accounts.current(e.tokens["learner"]).id
        c.exec_driver_sql(
            "INSERT INTO proof_attempts VALUES (1,?,1,?)",
            (
                owner,
                json.dumps(
                    {
                        "criteria": [
                            {"criterion_id": s["criterion_id"]} for s in reversed(SPEC)
                        ]
                    }
                ),
            ),
        )
        c.exec_driver_sql(
            "CREATE TABLE evaluation_results(id TEXT PRIMARY "
            "KEY,attempt_id INTEGER NOT NULL UNIQUE REFERENCES "
            "proof_attempts(id),payload TEXT NOT NULL)"
        )
        c.exec_driver_sql(
            "CREATE TABLE evaluation_criteria(result_id TEXT NOT "
            "NULL REFERENCES evaluation_results(id) DEFERRABLE "
            "INITIALLY DEFERRED,criterion_id TEXT NOT NULL,position"
            " INTEGER NOT NULL CHECK(position BETWEEN 0 AND "
            "7),PRIMARY "
            "KEY(result_id,criterion_id),UNIQUE(result_id,position))"
        )
        c.exec_driver_sql(
            "CREATE TABLE mentor_feedback(id TEXT PRIMARY "
            "KEY,result_id TEXT NOT NULL UNIQUE REFERENCES "
            "evaluation_results(id),payload TEXT NOT NULL)"
        )
        for table in ("evaluation_results", "evaluation_criteria", "mentor_feedback"):
            for op in ("UPDATE", "DELETE"):
                c.exec_driver_sql(
                    f"CREATE TRIGGER {table}_no_{op} BEFORE {op} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable'); END"
                )
        c.exec_driver_sql("""
        CREATE TRIGGER detail_insert BEFORE INSERT ON evaluation_criteria WHEN
        EXISTS(SELECT 1 FROM evaluation_results WHERE id=NEW.result_id) OR
        EXISTS(SELECT 1 FROM evaluation_criteria WHERE result_id=NEW.result_id
        AND (criterion_id=NEW.criterion_id OR position=NEW.position)) BEGIN
        SELECT RAISE(ABORT,'sealed or duplicate detail'); END
        """)
        c.exec_driver_sql("""
        CREATE TRIGGER result_insert BEFORE INSERT ON evaluation_results WHEN
        EXISTS(SELECT 1 FROM evaluation_results WHERE id=NEW.id OR
        attempt_id=NEW.attempt_id) OR NOT EXISTS(SELECT 1 FROM proof_attempts
        WHERE id=NEW.attempt_id AND completed=1) OR json_valid(NEW.payload)=0
        OR (SELECT count(*) FROM evaluation_criteria WHERE result_id=NEW.id)
        != (SELECT json_array_length(rubric,'$.criteria') FROM proof_attempts
        WHERE id=NEW.attempt_id) OR json_array_length(NEW.payload) != (SELECT
        count(*) FROM evaluation_criteria WHERE result_id=NEW.id) OR
        EXISTS(SELECT 1 FROM proof_attempts a,json_each(a.rubric,'$.criteria')
        expected WHERE a.id=NEW.attempt_id AND NOT EXISTS(SELECT 1 FROM
        evaluation_criteria d WHERE d.result_id=NEW.id AND
        d.criterion_id=json_extract(expected.value,'$.criterion_id') AND
        d.position=(SELECT count(*) FROM json_each(a.rubric,'$.criteria') earlier
        JOIN proof_registry reg ON
        reg.criterion_id=json_extract(earlier.value,'$.criterion_id')
        WHERE reg.ordinal < (SELECT ordinal FROM proof_registry WHERE
        criterion_id=json_extract(expected.value,'$.criterion_id'))))) OR
        EXISTS(SELECT 1 FROM evaluation_criteria d WHERE d.result_id=NEW.id
        AND NOT EXISTS(SELECT 1 FROM json_each(NEW.payload) j WHERE
        d.criterion_id=json_extract(j.value,'$.criterion_id') AND
        d.position=json_extract(j.value,'$.position'))) BEGIN SELECT
        RAISE(ABORT,'incomplete or inconsistent seal'); END
        """)
        c.exec_driver_sql("""
        CREATE TRIGGER feedback_insert BEFORE INSERT ON mentor_feedback WHEN
        EXISTS(SELECT 1 FROM mentor_feedback WHERE id=NEW.id OR
        result_id=NEW.result_id) BEGIN SELECT RAISE(ABORT,'feedback
        replacement'); END
        """)
    return e


def rows(e):
    with e.database.engine.connect() as c:
        assert not c.exec_driver_sql("PRAGMA foreign_key_check").all()
        return tuple(
            c.exec_driver_sql("SELECT count(*) FROM " + t).scalar_one()
            for t in ("evaluation_results", "evaluation_criteria", "mentor_feedback")
        )


def details(db, result_id, spec=SPEC):
    # Explicit Core statements cannot be reordered by relationship autoflush.
    for s in spec:
        db.execute(
            text("INSERT INTO evaluation_criteria VALUES (:r,:c,:p)"),
            {"r": result_id, "c": s["criterion_id"], "p": s["position"]},
        )


def parent(db, result_id, payload=SPEC):
    db.execute(
        text("INSERT INTO evaluation_results VALUES (:r,1,:p)"),
        {"r": result_id, "p": json.dumps(payload)},
    )


def insert(e, result_id):
    with e.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        actor = e.accounts.require(db, e.tokens["learner"], Role.LEARNER)
        owner = db.execute(
            text("SELECT learner_id FROM proof_attempts WHERE id=1")
        ).scalar_one()
        assert actor.id == owner
        existing = db.execute(
            text("SELECT id FROM evaluation_results WHERE attempt_id=1")
        ).scalar_one_or_none()
        if existing:
            return existing
        details(db, result_id)
        parent(db, result_id)
    return result_id


def test_order_seal_and_transaction(proof):
    assert insert(proof, "one") == "one"
    inserts = [s for s in proof.trace if s.startswith("INSERT INTO evaluation_")]
    assert ["criteria" if "criteria" in s else "result" for s in inserts] == [
        "criteria",
        "criteria",
        "result",
    ]
    assert rows(proof) == (1, 2, 0)
    assert insert(proof, "retry") == "one" and rows(proof) == (1, 2, 0)


@pytest.mark.parametrize(
    "spec",
    [
        (),
        SPEC[:1],
        SPEC + ({"criterion_id": "email.link", "position": 2},),
        (SPEC[0], SPEC[0]),
        (SPEC[0], {"criterion_id": "email.link", "position": 1}),
        (
            {"criterion_id": "email.sender", "position": 1},
            {"criterion_id": "web.address", "position": 0},
        ),
    ],
)
def test_incomplete_wrong_and_duplicate_rollback(proof, spec):
    with pytest.raises(IntegrityError), proof.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        details(db, "bad", spec)
        parent(db, "bad")
    assert rows(proof) == (0, 0, 0)


@pytest.mark.parametrize(
    "stage",
    ["orphan", "after_details", "after_parent", "parent_first", "lying_envelope"],
)
def test_failed_commit_and_full_rollback(proof, stage):
    expected = (
        RuntimeError if stage in ("after_details", "after_parent") else IntegrityError
    )
    with pytest.raises(expected), proof.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        if stage == "parent_first":
            parent(db, "bad")
        details(db, "bad")
        if stage == "after_details":
            raise RuntimeError("forced")
        if stage != "orphan":
            parent(db, "bad", payload=() if stage == "lying_envelope" else SPEC)
        if stage == "after_parent":
            raise RuntimeError("forced")
    assert rows(proof) == (0, 0, 0)
    assert insert(proof, "recovered") == "recovered"


@pytest.mark.parametrize("recursive", [0, 1])
@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO evaluation_criteria VALUES ('one','email.link',2)",
        "UPDATE evaluation_criteria SET position=2 WHERE position=0",
        "DELETE FROM evaluation_criteria",
        "UPDATE evaluation_results SET payload='[]'",
        "DELETE FROM evaluation_results",
        "INSERT OR REPLACE INTO evaluation_results VALUES ('one',1,'[]')",
        "INSERT OR REPLACE INTO evaluation_results VALUES ('other',1,'[]')",
        "INSERT OR REPLACE INTO evaluation_criteria VALUES ('one','email.sender',0)",
        "INSERT OR REPLACE INTO evaluation_criteria VALUES ('one','email.link',0)",
        (
            "INSERT INTO evaluation_results VALUES ('one',1,'[]') "
            "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload"
        ),
        (
            "INSERT INTO evaluation_criteria VALUES "
            "('one','email.sender',0) ON "
            "CONFLICT(result_id,criterion_id) DO UPDATE SET "
            "position=excluded.position"
        ),
        "INSERT OR REPLACE INTO mentor_feedback VALUES ('fb2','one','[]')",
        "INSERT OR REPLACE INTO mentor_feedback VALUES ('fb','one','[]')",
        "UPDATE mentor_feedback SET payload='[]'",
        "DELETE FROM mentor_feedback",
    ],
)
def test_post_seal_and_replace(proof, recursive, sql):
    insert(proof, "one")
    with proof.database.engine.begin() as c:
        c.exec_driver_sql("INSERT INTO mentor_feedback VALUES ('fb','one','{}')")
    with pytest.raises(IntegrityError), proof.database.engine.begin() as c:
        c.exec_driver_sql(f"PRAGMA recursive_triggers={recursive}")
        c.exec_driver_sql(sql)
    assert rows(proof) == (1, 2, 1)


def test_serialized_concurrent_winner(proof):
    barrier = Barrier(2)

    def worker(n):
        barrier.wait(timeout=10)
        return insert(proof, str(n))

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(worker, n) for n in range(2)]
        winners = [f.result(timeout=15) for f in futures]
    assert winners[0] == winners[1] and rows(proof) == (1, 2, 0)


def test_real_snapshot_before_authorization(proof):
    # WAL is scratch-only to allow writer commit while proving read isolation.
    with proof.database.engine.connect() as c:
        c.exec_driver_sql("PRAGMA journal_mode=WAL")
    proof.trace.clear()
    with proof.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN")
        actor = proof.accounts.require(db, proof.tokens["learner"], Role.LEARNER)
        owner = db.execute(
            text("SELECT learner_id FROM proof_attempts WHERE id=1")
        ).scalar_one()
        assert actor.id == owner
        insert(proof, "concurrent")
        assert (
            db.execute(text("SELECT count(*) FROM evaluation_results")).scalar_one()
            == 0
        )
        assert proof.trace[0] == "BEGIN"
        assert proof.trace[1].startswith("SELECT users.")
    assert rows(proof) == (1, 2, 0)


def test_authorization_before_protected_reads(proof):
    proof.trace.clear()
    with pytest.raises(AccessDenied), proof.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN")
        proof.accounts.require(db, proof.tokens["teacher"], Role.LEARNER)
        db.execute(text("SELECT * FROM evaluation_criteria"))
    assert not any("SELECT * FROM evaluation_" in s for s in proof.trace)


def test_account_snapshot_and_next_request_denial(proof):
    with proof.database.engine.connect() as c:
        c.exec_driver_sql("PRAGMA journal_mode=WAL")
    with proof.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN")
        actor = proof.accounts.require(db, proof.tokens["learner"], Role.LEARNER)
        with proof.database.engine.begin() as writer:
            writer.execute(
                text("UPDATE users SET active=0 WHERE id=:id"), {"id": actor.id}
            )
        # The authorization decision and all reads belong to the original snapshot.
        assert (
            db.execute(
                text("SELECT active FROM users WHERE id=:id"), {"id": actor.id}
            ).scalar_one()
            == 1
        )
        assert (
            db.execute(text("SELECT count(*) FROM evaluation_results")).scalar_one()
            == 0
        )
    with pytest.raises(AccessDenied), proof.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN")
        proof.accounts.require(db, proof.tokens["learner"], Role.LEARNER)


def test_ownership_before_details(proof):
    with proof.database.engine.begin() as db:
        other = proof.accounts.current(proof.tokens["other"]).id
        db.execute(
            text("UPDATE proof_attempts SET learner_id=:id WHERE id=1"), {"id": other}
        )
    proof.trace.clear()
    with pytest.raises(AccessDenied), proof.database.sessions.begin() as db:
        db.connection().exec_driver_sql("BEGIN")
        actor = proof.accounts.require(db, proof.tokens["learner"], Role.LEARNER)
        owner = db.execute(
            text("SELECT learner_id FROM proof_attempts WHERE id=1")
        ).scalar_one()
        if actor.id != owner:
            raise AccessDenied()
        db.execute(text("SELECT * FROM evaluation_criteria"))
    assert not any(
        "SELECT * FROM evaluation_criteria" in statement for statement in proof.trace
    )
