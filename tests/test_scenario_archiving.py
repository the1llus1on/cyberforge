"""Soft archive RBAC, additive upgrades, SQL guards, and independent editors."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from cyberforge.application.accounts import AccountService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import AccessDenied, ApplicationError
from cyberforge.persistence.database import Database


def context(scenario):
    return dict(
        expected_version=scenario.version,
        expected_revision=scenario.revision,
        expected_archive_revision=scenario.archive_revision,
    )


def create(env, actor="teacher"):
    return env.service.create(
        env.tokens[actor], dict(topic="Синтетичний сценарій", difficulty="beginner")
    )


def snapshots(database):
    with database.engine.connect() as db:
        return db.execute(text("SELECT * FROM scenario_versions ORDER BY id")).all()


def test_archive_restore_restart_and_idempotence(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    original = create(env)
    before = snapshots(env.database)
    archived = env.service.archive(token, original.id, **context(original))
    assert archived.archived and archived.archive_revision == 1
    assert env.service.catalog(token) == ()
    assert env.service.catalog(token, archived=True) == (archived,)
    assert env.service.catalog(token, archived=None) == (archived,)
    assert env.service.archive(token, original.id, **context(archived)) == archived
    assert env.service.get(token, original.id, version=1) == archived
    with pytest.raises(ApplicationError, match="архівовано"):
        env.service.update(token, original.id, original.parameters, **context(archived))
    independent = Database(Path(env.database.engine.url.database))
    independent.upgrade()
    try:
        accounts = AccountService(independent)
        service = ScenarioService(accounts)
        login = accounts.login("teacher", env.password)
        assert service.get(login, original.id) == archived
        restored = service.restore(login, original.id, **context(archived))
        assert not restored.archived and restored.archive_revision == 2
        assert service.restore(login, original.id, **context(restored)) == restored
        assert (
            restored.id,
            restored.owner_id,
            restored.created_at,
            restored.parameters,
            restored.version,
            restored.revision,
            restored.updated_at,
        ) == (
            original.id,
            original.owner_id,
            original.created_at,
            original.parameters,
            original.version,
            original.revision,
            original.updated_at,
        )
        assert snapshots(independent) == before
    finally:
        independent.close()


@pytest.mark.parametrize("actor", [None, "learner", "other", "admin", "invalid"])
@pytest.mark.parametrize("operation", ["archive", "restore"])
def test_archive_forbidden_paths(scenario_env, actor, operation):
    env = scenario_env
    original = create(env)
    if operation == "restore":
        original = env.service.archive(
            env.tokens["teacher"], original.id, **context(original)
        )
    token = env.tokens.get(actor, "forged-token") if actor else None
    for scenario_id in (original.id, 99999):
        with pytest.raises(AccessDenied):
            getattr(env.service, operation)(token, scenario_id, **context(original))
    if actor == "admin":
        assert env.service.get(token, original.id) == original
        assert env.service.catalog(token, archived=original.archived) == (original,)
    assert env.service.get(env.tokens["teacher"], original.id) == original


def test_admin_own_archive_and_revoked_session(scenario_env):
    env = scenario_env
    original = create(env, "admin")
    token = env.tokens["admin"]
    archived = env.service.archive(token, original.id, **context(original))
    assert (
        env.service.restore(token, original.id, **context(archived)).archive_revision
        == 2
    )
    teacher = create(env)
    env.accounts.logout(env.tokens["teacher"])
    for operation in ("archive", "restore"):
        with pytest.raises(AccessDenied):
            getattr(env.service, operation)(
                env.tokens["teacher"], teacher.id, **context(teacher)
            )


def test_archive_preserves_all_versions_and_published_json(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    original = create(env)
    with env.database.engine.begin() as db:
        db.execute(
            text(
                "UPDATE scenario_versions SET status='published' WHERE scenario_id=:id"
            ),
            {"id": original.id},
        )
    draft = env.service.update(
        token,
        original.id,
        original.parameters.model_dump() | {"topic": "Наступна чернетка"},
        **context(original),
    )
    before = snapshots(env.database)
    archived = env.service.archive(token, draft.id, **context(draft))
    restored = env.service.restore(token, draft.id, **context(archived))
    assert restored.version == 2 and restored.revision == 1
    assert env.service.get(token, draft.id, version=1).status == "published"
    assert snapshots(env.database) == before
    for statement in (
        "UPDATE scenario_versions SET parameters='{}' WHERE status='published'",
        "DELETE FROM scenario_versions WHERE status='published'",
    ):
        with pytest.raises(IntegrityError), env.database.engine.begin() as db:
            db.execute(text(statement))


def test_sql_identity_guards_and_permitted_metadata(scenario_env):
    env = scenario_env
    original = create(env)
    for field, value in (
        ("id", "999"),
        ("owner_id", "999"),
        ("created_at", "'2001-01-01'"),
        ("archived_at", "'invalid date'"),
        ("archive_revision", "-1"),
        ("archive_revision", "1"),
    ):
        with pytest.raises(IntegrityError), env.database.engine.begin() as db:
            db.execute(text(f"UPDATE scenarios SET {field}={value}"))
    with env.database.engine.begin() as db:
        db.execute(
            text("UPDATE scenarios SET id=id, owner_id=owner_id, created_at=created_at")
        )
        db.execute(
            text(
                "UPDATE scenarios SET archived_at='2026-11-12 09:00:00', "
                "archive_revision=1"
            )
        )
    assert env.service.get(env.tokens["teacher"], original.id).archived
    with pytest.raises(IntegrityError), env.database.engine.begin() as db:
        db.execute(text("UPDATE scenarios SET archived_at=NULL"))
    with env.database.engine.begin() as db:
        db.execute(text("UPDATE scenarios SET archived_at=NULL, archive_revision=2"))
    assert not env.service.get(env.tokens["teacher"], original.id).archived


@pytest.mark.parametrize("operation", ["archive", "restore"])
def test_archive_failure_rolls_back(scenario_env, operation):
    env = scenario_env
    original = create(env)
    if operation == "restore":
        original = env.service.archive(
            env.tokens["teacher"], original.id, **context(original)
        )
    before = snapshots(env.database)
    with env.database.engine.begin() as db:
        db.execute(
            text(
                "CREATE TRIGGER fail_archive BEFORE UPDATE ON scenarios "
                "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
            )
        )
    with pytest.raises(ApplicationError):
        getattr(env.service, operation)(
            env.tokens["teacher"], original.id, **context(original)
        )
    assert env.service.get(env.tokens["teacher"], original.id) == original
    assert snapshots(env.database) == before


def test_existing_phase3_upgrade_preserves_raw_snapshots_and_table(tmp_path):
    database = Database(tmp_path / "existing-phase3.sqlite3")
    config = database.migration_config()
    with database.engine.begin() as db:
        config.attributes["connection"] = db
        command.upgrade(config, "0002_scenarios")
    accounts = AccountService(database)
    owner = accounts.bootstrap("admin", "Синтетичний автор", "synthetic-password-123")
    payload = json.dumps(
        dict(
            topic="Збережений сценарій",
            difficulty="beginner",
            nist_cues=["власний текст", "Spelling and grammar irregularities"],
        ),
        ensure_ascii=False,
    )
    with database.engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO scenarios(id,owner_id,created_at) "
                "VALUES (42,:owner,'2026-11-11 12:00:00')"
            ),
            {"owner": owner.id},
        )
        for number, status in ((1, "published"), (2, "draft")):
            db.execute(
                text(
                    "INSERT INTO scenario_versions "
                    "(scenario_id,number,revision,status,parameters,"
                    "created_at,updated_at) "
                    "VALUES (42,:n,3,:s,:p,'2026-11-11 12:00:00','2026-11-11 13:00:00')"
                ),
                {"n": number, "s": status, "p": payload},
            )
        users = db.execute(text("SELECT * FROM users")).all()
        rootpage = db.execute(
            text("SELECT rootpage FROM sqlite_master WHERE name='scenarios'")
        ).scalar()
    before = snapshots(database)
    database.upgrade()
    database.upgrade()
    with database.engine.connect() as db:
        assert db.execute(text("SELECT * FROM users")).all() == users
        assert (
            db.execute(
                text("SELECT rootpage FROM sqlite_master WHERE name='scenarios'")
            ).scalar()
            == rootpage
        )
        assert db.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert snapshots(database) == before
    service = ScenarioService(accounts)
    token = accounts.login("admin", "synthetic-password-123")
    saved = service.get(token, 42)
    assert saved.id == 42 and saved.version == 2 and saved.revision == 3
    assert service.archive(token, 42, **context(saved)).archived
    database.close()


def test_independent_database_sessions_compete(scenario_env):
    env = scenario_env
    original = create(env)
    independent = Database(Path(env.database.engine.url.database))
    accounts = AccountService(independent)
    token = accounts.login("teacher", env.password)
    other = ScenarioService(accounts)
    barrier = Barrier(2)

    def save(service, login, topic):
        snapshot = service.get(login, original.id)
        barrier.wait(timeout=10)
        try:
            return service.update(
                login,
                original.id,
                snapshot.parameters.model_dump() | {"topic": topic},
                **context(snapshot),
            )
        except ApplicationError:
            return None

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = [
                workers.submit(save, service, login, topic)
                for service, login, topic in (
                    (env.service, env.tokens["teacher"], "Перший редактор"),
                    (other, token, "Другий редактор"),
                )
            ]
            results = [future.result(timeout=20) for future in results]
        assert sum(result is not None for result in results) == 1
        winner = next(result for result in results if result)
        assert other.get(token, original.id) == winner
        assert len(snapshots(independent)) == 1
        archived = other.archive(token, winner.id, **context(winner))
        restored = other.restore(token, winner.id, **context(archived))
        with pytest.raises(ApplicationError, match="уже змінено"):
            env.service.update(
                env.tokens["teacher"], winner.id, winner.parameters, **context(winner)
            )
        assert env.service.get(env.tokens["teacher"], winner.id) == restored
    finally:
        independent.close()


def test_independent_processes_compete(scenario_env):
    env = scenario_env
    original = create(env)
    script = """
import json,sys
from pathlib import Path
from cyberforge.persistence.database import Database
from cyberforge.application.accounts import AccountService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import ApplicationError
value=json.load(sys.stdin)
database=Database(Path(value["path"]))
accounts=AccountService(database)
token=accounts.login("teacher", value["password"])
try:
    saved=ScenarioService(accounts).update(token,value["id"],dict(topic=value["topic"],difficulty="beginner"),expected_version=1,expected_revision=1,expected_archive_revision=0)
    print(json.dumps(dict(saved=True,topic=saved.parameters.topic)))
except ApplicationError:
    print(json.dumps(dict(saved=False,retained=value["topic"])))
finally:
    database.close()
"""

    def run(topic):
        result = subprocess.run(
            [sys.executable, "-I", "-c", script],
            input=json.dumps(
                dict(
                    path=env.database.engine.url.database,
                    password=env.password,
                    id=original.id,
                    topic=topic,
                )
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            env={**os.environ, "PYTHONUTF8": "1"},
            check=True,
        )
        return json.loads(result.stdout)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = tuple(workers.map(run, ("Процес один", "Процес два")))
    assert sum(result["saved"] for result in results) == 1
    assert next(result["retained"] for result in results if not result["saved"])
    assert env.service.get(env.tokens["teacher"], original.id).parameters.topic == next(
        result["topic"] for result in results if result["saved"]
    )
    assert len(snapshots(env.database)) == 1


def test_archived_draft_cannot_be_changed_by_direct_sql(scenario_env):
    env = scenario_env
    original = create(env)
    env.service.archive(env.tokens["teacher"], original.id, **context(original))
    before = snapshots(env.database)
    for statement in (
        "UPDATE scenario_versions SET parameters='{}'",
        "DELETE FROM scenario_versions",
        "INSERT INTO scenario_versions "
        "(scenario_id,number,revision,status,parameters,created_at,updated_at) "
        "SELECT scenario_id,2,1,status,parameters,created_at,updated_at "
        "FROM scenario_versions",
    ):
        with pytest.raises(IntegrityError), env.database.engine.begin() as db:
            db.execute(text(statement))
    assert snapshots(env.database) == before


def test_deactivation_denies_archive_restore_and_reads(scenario_env):
    env = scenario_env
    original = create(env)
    token = env.tokens["teacher"]
    actor = env.accounts.current(token)
    env.accounts.update_user(
        env.tokens["admin"], actor.id, actor.display_name, actor.role, False
    )
    for operation in ("archive", "restore"):
        with pytest.raises(AccessDenied):
            getattr(env.service, operation)(token, original.id, **context(original))
    with pytest.raises(AccessDenied):
        env.service.catalog(token, archived=None)
    with pytest.raises(AccessDenied):
        env.service.get(token, original.id)
