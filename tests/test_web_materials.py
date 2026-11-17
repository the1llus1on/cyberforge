"""Service RBAC, exact Email binding, transactional persistence and migration."""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from cyberforge.application.accounts import AccountService
from cyberforge.application.email_materials import EmailMaterialService, MaterialState
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.factory import create_gateway
from cyberforge.persistence.database import Database
from cyberforge.persistence.models import Base
from cyberforge.web.contracts import WebPageV2


@pytest.fixture
def web_env(scenario_env, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected cloud/network call")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    env = scenario_env
    env.token = env.tokens["teacher"]
    env.emails = EmailMaterialService(env.service, create_gateway(), demo=True)
    env.web = WebMaterialService(env.emails, demo=True)
    env.scenario = env.service.create(
        env.token, dict(topic="Навчальний сайт", difficulty="beginner")
    )
    email_workspace = env.emails.load(env.token, env.scenario)
    email = env.emails.generate(env.token, email_workspace)
    env.saved_email = env.emails.save(env.token, email_workspace, email)
    env.workspace = env.web.load(env.token, env.scenario)
    return env


def persisted(env):
    with env.database.engine.connect() as db:
        return db.execute(text("SELECT * FROM web_materials")).all()


def test_explicit_save_reopen_restart_and_inspected_payload(web_env):
    env = web_env
    draft = env.web.generate(env.token, env.workspace)
    assert persisted(env) == []
    saved = env.web.save(env.token, env.workspace, draft)
    assert saved.state == MaterialState.SAVED
    assert saved == env.web.load(env.token, env.scenario)
    other_db = Database(Path(env.database.engine.url.database))
    try:
        accounts = AccountService(other_db)
        token = accounts.login("teacher", env.password)
        service = WebMaterialService(
            EmailMaterialService(ScenarioService(accounts), create_gateway())
        )
        assert service.load(token, env.scenario) == saved
    finally:
        other_db.close()


def test_saved_email_required(web_env):
    env = web_env
    scenario = env.service.create(
        env.token, dict(topic="Без листа", difficulty="beginner")
    )
    workspace = env.web.load(env.token, scenario)
    assert workspace.email is None
    with pytest.raises(ApplicationError, match="збережіть"):
        env.web.generate(env.token, workspace)


def test_edited_email_context_is_authoritative_and_changes_make_web_stale(web_env):
    env = web_env
    draft = env.saved_email.draft
    changed = env.emails.edit(
        env.token,
        env.saved_email,
        draft,
        index=0,
        message=draft.slots.main.model_copy(
            update={"sender_name": "Навчальний редактор"}
        ),
    )
    env.emails.save(env.token, env.saved_email, changed)
    workspace = env.web.load(env.token, env.scenario)
    web = env.web.generate(env.token, workspace)
    assert web.context.sender_name == "Навчальний редактор"
    saved = env.web.save(env.token, workspace, web)
    old_rows = persisted(env)
    email_workspace = env.emails.load(env.token, env.scenario)
    edited = env.emails.edit(
        env.token,
        email_workspace,
        changed,
        index=0,
        message=changed.slots.main.model_copy(update={"subject": "Змінений лист"}),
    )
    env.emails.save(env.token, email_workspace, edited)
    stale = env.web.load(env.token, env.scenario)
    assert stale.state == MaterialState.REVIEW and stale.draft == web
    assert persisted(env) == old_rows
    for operation in (
        lambda: env.web.save(env.token, saved, web),
        lambda: env.web.generate(env.token, saved, previous=web),
        lambda: env.web.generate(env.token, stale, previous=web),
    ):
        with pytest.raises(ApplicationError):
            operation()
    regenerated = env.web.generate(env.token, stale)
    assert regenerated.email_binding != web.email_binding
    assert persisted(env) == old_rows
    assert env.web.save(env.token, stale, regenerated).state == MaterialState.SAVED


@pytest.mark.parametrize("name", ["other", "learner", "admin"])
def test_forbidden_roles_and_other_owner_writes(web_env, name):
    env = web_env
    draft = env.web.generate(env.token, env.workspace)
    token = env.tokens[name]
    if name == "admin":
        assert env.web.load(token, env.scenario).email is not None
    else:
        with pytest.raises(ApplicationError):
            env.web.load(token, env.scenario)
    for operation in (
        lambda: env.web.generate(token, env.workspace),
        lambda: env.web.save(token, env.workspace, draft),
        lambda: env.web.edit(token, env.workspace, draft, draft.page),
    ):
        with pytest.raises(ApplicationError):
            operation()
    assert persisted(env) == []


@pytest.mark.parametrize("change", ["id", "version", "digest", "context", "email"])
def test_cross_identity_and_forged_sources_rejected(web_env, change):
    env = web_env
    draft = env.web.generate(env.token, env.workspace)
    payload = draft.model_dump(mode="json")
    if change == "id":
        payload["scenario_id"] += 1
    elif change == "version":
        payload["scenario_version"] += 1
    elif change == "digest":
        payload["source_digest"] = "0" * 64
    elif change == "context":
        payload["context"]["sender_name"] = "Інший"
    else:
        payload["email_binding"]["revision"] += 1
    forged = draft.model_copy(update=payload)
    with pytest.raises(ApplicationError):
        env.web.save(env.token, env.workspace, forged)
    assert persisted(env) == []


def test_manual_edit_unsaved_and_optimistic_conflict(web_env):
    env = web_env
    draft = env.web.generate(env.token, env.workspace)
    saved = env.web.save(env.token, env.workspace, draft)
    data = draft.page.model_dump(mode="json")
    data["components"][1]["text"] = "Ручна правка"
    page = WebPageV2.model_validate_json(json.dumps(data))
    candidate = env.web.edit(env.token, saved, draft, page)
    assert env.web.load(env.token, env.scenario).draft == draft
    assert env.web.save(env.token, saved, candidate).revision == 2
    with pytest.raises(ApplicationError):
        env.web.save(env.token, saved, draft)


@pytest.mark.parametrize("state", ["archived", "published"])
def test_immutable_versions_archive_and_database_triggers(web_env, state):
    env = web_env
    draft = env.web.generate(env.token, env.workspace)
    env.web.save(env.token, env.workspace, draft)
    if state == "archived":
        scenario = env.service.archive(
            env.token,
            env.scenario.id,
            expected_version=1,
            expected_revision=1,
            expected_archive_revision=0,
        )
    else:
        with env.database.engine.begin() as db:
            db.execute(text("UPDATE scenario_versions SET status='published'"))
        scenario = env.service.get(env.token, env.scenario.id)
    workspace = env.web.load(env.token, scenario)
    assert workspace.draft == draft
    with pytest.raises(ApplicationError):
        env.web.generate(env.token, workspace, previous=draft)
    with pytest.raises(ApplicationError):
        env.web.save(env.token, workspace, draft)
    with pytest.raises(IntegrityError), env.database.engine.begin() as db:
        db.execute(text("DELETE FROM web_materials"))


def test_new_version_does_not_copy_materials(web_env):
    env = web_env
    draft = env.web.generate(env.token, env.workspace)
    env.web.save(env.token, env.workspace, draft)
    with env.database.engine.begin() as db:
        db.execute(text("UPDATE scenario_versions SET status='published'"))
    scenario = env.service.update(
        env.token,
        env.scenario.id,
        dict(topic="Нова версія", difficulty="beginner"),
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=0,
    )
    assert scenario.version == 2
    workspace = env.web.load(env.token, scenario)
    assert workspace.draft is None and workspace.email is None
    assert env.web.load(env.token, env.scenario).draft == draft


def test_migration_preserves_email_and_safe_downgrade(web_env):
    env = web_env
    config = env.database.migration_config()
    with env.database.engine.begin() as db:
        config.attributes["connection"] = db
        command.downgrade(config, "0004_email_materials")
    assert env.emails.load(env.token, env.scenario) == env.saved_email
    env.database.upgrade()
    with env.database.engine.connect() as db:
        context = MigrationContext.configure(db)
        assert context.get_current_revision() == "0008_evaluations"
        assert compare_metadata(context, Base.metadata) == []
        assert db.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    draft = env.web.generate(env.token, env.workspace)
    env.web.save(env.token, env.workspace, draft)
    before = persisted(env)
    with pytest.raises(RuntimeError), env.database.engine.begin() as db:
        config.attributes["connection"] = db
        command.downgrade(config, "0004_email_materials")
    assert persisted(env) == before


def test_two_concurrent_saves_have_one_winner(web_env):
    env = web_env
    draft = env.web.generate(env.token, env.workspace)
    barrier = Barrier(2)

    def save():
        barrier.wait(timeout=5)
        try:
            env.web.save(env.token, env.workspace, draft)
            return "saved"
        except ApplicationError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: save(), range(2))) == ["conflict", "saved"]
    assert len(persisted(env)) == 1


def test_generation_rechecks_email_after_worker_completes(web_env, monkeypatch):
    env = web_env
    from cyberforge.agents.web import WebScenarioAgentV2

    original = WebScenarioAgentV2.run

    def concurrent_change(agent, source):
        result = original(agent, source)
        env.emails.save(env.token, env.saved_email, env.saved_email.draft)
        return result

    monkeypatch.setattr(WebScenarioAgentV2, "run", concurrent_change)
    with pytest.raises(ApplicationError):
        env.web.generate(env.token, env.workspace)
    assert persisted(env) == []
