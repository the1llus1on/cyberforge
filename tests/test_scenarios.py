"""Scenario validation, ownership, transactional drafts, and durable identity."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from cyberforge.application.accounts import AccountService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.domain.scenarios import Difficulty, ScenarioParameters, ScenarioStatus
from cyberforge.persistence.database import Database
from cyberforge.persistence.models import ScenarioVersion


def parameters(**changes):
    return dict(topic="Синтетична служба підтримки", difficulty="beginner", **changes)


@pytest.mark.parametrize(
    "change",
    [
        {"topic": " \n "},
        {"topic": "x" * 2001},
        {"topic": 12},
        {"difficulty": "expert"},
        {"audience": "x" * 1001},
        {"description": "x" * 10001},
        {"learning_objective": "x" * 10001},
        {"tactics": [""]},
        {"nist_cues": ["x" * 201]},
        {"generation_parameters": []},
        {"status": "published"},
        {"owner_id": 999},
        {"id": 999},
    ],
)
def test_parameter_validation(change):
    with pytest.raises(ValidationError):
        ScenarioParameters.model_validate(parameters() | change)


def test_create_unique_persistent_ids_and_complete_parameters(
    scenario_env, monkeypatch
):
    import socket

    def no_network(*args, **kwargs):
        pytest.fail("Scenario management must work without network")

    monkeypatch.setattr(socket, "create_connection", no_network)
    env = scenario_env
    payload = parameters(
        audience="Синтетична група",
        description="Навчальна ситуація",
        learning_objective="Розпізнати підозріле повідомлення",
        tactics=("Терміновість",),
        nist_cues=("B.1.1",),
        generation_parameters={"language": "uk", "nested": [1, True, None]},
    )
    first = env.service.create(env.tokens["teacher"], payload)
    second = env.service.create(env.tokens["teacher"], parameters())
    assert first.id != second.id and first.name == f"Сценарій {first.id}"
    assert first.status == ScenarioStatus.DRAFT
    assert (first.version, first.revision) == (1, 1)
    assert first.parameters.model_dump(mode="json") == ScenarioParameters(
        **payload
    ).model_dump(mode="json")
    assert first.created_at.tzinfo is not None
    path = env.database.engine.url.database
    env.database.close()
    reopened = Database(Path(path))
    reopened.upgrade()
    try:
        accounts = AccountService(reopened)
        token = accounts.login("teacher", env.password)
        service = ScenarioService(accounts)
        assert service.get(token, first.id) == first
        assert [s.id for s in service.catalog(token)] == [second.id, first.id]
        assert service.create(token, parameters()).id > second.id
    finally:
        reopened.close()


def test_draft_update_conflict_and_validation_atomicity(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    first = env.service.create(token, parameters())
    with pytest.raises(ApplicationError):
        env.service.update(
            token,
            first.id,
            parameters() | {"topic": ""},
            expected_version=1,
            expected_revision=1,
        )
    assert env.service.get(token, first.id) == first
    changed = env.service.update(
        token,
        first.id,
        parameters() | {"topic": "Нова тема"},
        expected_version=1,
        expected_revision=1,
    )
    assert changed.id == first.id and changed.version == 1 and changed.revision == 2
    assert changed.created_at == first.created_at
    with pytest.raises(ApplicationError, match="уже змінено"):
        env.service.update(
            token, first.id, parameters(), expected_version=1, expected_revision=1
        )
    assert env.service.get(token, first.id) == changed
    assert (
        env.service.update(
            token, first.id, changed.parameters, expected_version=1, expected_revision=2
        )
        == changed
    )


@pytest.mark.parametrize("actor", [None, "learner", "other"])
def test_private_scenario_forbidden_paths(scenario_env, actor):
    env = scenario_env
    owner = env.tokens["teacher"]
    scenario = env.service.create(owner, parameters())
    token = env.tokens.get(actor)
    for version in (None, 1):
        with pytest.raises(AccessDenied):
            env.service.get(token, scenario.id, version=version)
    with pytest.raises(AccessDenied):
        env.service.update(
            token, scenario.id, parameters(), expected_version=1, expected_revision=1
        )
    if actor == "other":
        assert env.service.catalog(token) == ()
    else:
        with pytest.raises(AccessDenied):
            env.service.catalog(token)
        with pytest.raises(AccessDenied):
            env.service.create(token, parameters())
    assert env.service.get(owner, scenario.id) == scenario


def test_admin_views_all_but_edits_own_and_revoked_sessions(scenario_env):
    env = scenario_env
    admin, teacher = env.tokens["admin"], env.tokens["teacher"]
    foreign = env.service.create(teacher, parameters())
    own = env.service.create(admin, parameters())
    assert {s.id for s in env.service.catalog(admin)} == {own.id, foreign.id}
    assert env.service.get(admin, foreign.id) == foreign
    with pytest.raises(AccessDenied):
        env.service.update(
            admin, foreign.id, parameters(), expected_version=1, expected_revision=1
        )
    actor = env.accounts.current(teacher)
    with pytest.raises(ApplicationError, match="пов’язані"):
        env.accounts.delete_user(admin, actor.id)
    env.accounts.update_user(
        admin, actor.id, actor.display_name, Role.INSTRUCTOR, False
    )
    for action in (
        lambda: env.service.catalog(teacher),
        lambda: env.service.get(teacher, foreign.id),
        lambda: env.service.create(teacher, parameters()),
        lambda: env.service.update(
            teacher, foreign.id, parameters(), expected_version=1, expected_revision=1
        ),
    ):
        with pytest.raises(AccessDenied):
            action()


def test_published_snapshot_forks_only_on_change(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    scenario = env.service.create(token, parameters())
    # Fixture only: there is deliberately no Phase 3 publishing API.
    with env.database.sessions.begin() as db:
        row = db.scalar(
            select(ScenarioVersion).where(ScenarioVersion.scenario_id == scenario.id)
        )
        row.status = "published"
    published = env.service.get(token, scenario.id)
    assert (
        env.service.update(
            token,
            scenario.id,
            published.parameters,
            expected_version=1,
            expected_revision=1,
        )
        == published
    )
    draft = env.service.update(
        token,
        scenario.id,
        parameters() | {"topic": "Наступна чернетка"},
        expected_version=1,
        expected_revision=1,
    )
    assert (draft.id, draft.version, draft.revision, draft.status) == (
        scenario.id,
        2,
        1,
        ScenarioStatus.DRAFT,
    )
    assert env.service.get(token, scenario.id, version=1) == published
    assert env.service.catalog(token) == (draft,)
    for sql in (
        "UPDATE scenario_versions SET status='draft' WHERE number=1",
        "DELETE FROM scenario_versions WHERE number=1",
        "UPDATE scenarios SET owner_id=999",
    ):
        with pytest.raises(IntegrityError), env.database.engine.begin() as db:
            db.execute(text(sql))


def test_concurrent_edit_does_not_overwrite(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    scenario = env.service.create(token, parameters())

    def save(topic):
        try:
            return env.service.update(
                token,
                scenario.id,
                parameters() | {"topic": topic},
                expected_version=1,
                expected_revision=1,
            )
        except ApplicationError:
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = tuple(workers.map(save, ("Перша правка", "Друга правка")))
    assert sum(result is not None for result in results) == 1
    assert env.service.get(token, scenario.id) == next(r for r in results if r)


def test_concurrent_creates_and_database_version_constraints(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    with ThreadPoolExecutor(max_workers=3) as workers:
        records = tuple(
            workers.map(lambda _: env.service.create(token, parameters()), range(3))
        )
    assert len({record.id for record in records}) == 3
    for statement in (
        "UPDATE scenario_versions SET number=0",
        "UPDATE scenario_versions SET revision=0",
        "UPDATE scenario_versions SET scenario_id=999",
        "UPDATE scenario_versions SET status='ready'",
        "INSERT INTO scenario_versions "
        "(scenario_id,number,revision,status,parameters,created_at,updated_at) "
        "SELECT scenario_id,number,revision,status,parameters,created_at,updated_at "
        "FROM scenario_versions LIMIT 1",
    ):
        with pytest.raises(IntegrityError), env.database.engine.begin() as db:
            db.execute(text(statement))


def test_upgrade_existing_phase2_database_preserves_identity_and_groups(tmp_path):
    database = Database(tmp_path / "phase2.sqlite3")
    config = database.migration_config()
    with database.engine.begin() as db:
        config.attributes["connection"] = db
        command.upgrade(config, "0001_users_groups")
    accounts = AccountService(database)
    accounts.bootstrap("admin", "Синтетичний адміністратор", "synthetic-password-123")
    with database.engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO learning_groups(name, description) "
                "VALUES ('Тест', 'Зберегти')"
            )
        )
        before = db.execute(text("SELECT * FROM users")).all()
    database.upgrade()
    database.upgrade()
    with database.engine.connect() as db:
        assert db.execute(text("SELECT * FROM users")).all() == before
        assert (
            db.execute(text("SELECT description FROM learning_groups")).scalar()
            == "Зберегти"
        )
        assert db.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert "scenario_versions" in inspect(db).get_table_names()
    database.close()


def test_bounded_json_and_model_revalidation(scenario_env):
    env = scenario_env
    token = env.tokens["teacher"]
    for extra in ({"large": "x" * 50001}, {"bad": float("nan")}):
        with pytest.raises(ApplicationError):
            env.service.create(token, parameters(generation_parameters=extra))
    forged = ScenarioParameters.model_construct(
        topic="", difficulty=Difficulty.BEGINNER
    )
    with pytest.raises(ApplicationError):
        env.service.create(token, forged)
    assert env.service.catalog(token) == ()
