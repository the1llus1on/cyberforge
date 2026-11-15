"""Trusted Email boundary: persistence, migration, provenance, RBAC and gateway."""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.application.email_materials import (
    EmailMaterialService,
    MaterialState,
    email_source,
    synthetic_context,
)
from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import AccessDenied, ApplicationError
from cyberforge.llm.config import GatewayConfig, RateLimits
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    Provider,
    ProviderResponse,
)
from cyberforge.llm.factory import create_gateway
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.mock import MockLLMProvider
from cyberforge.persistence.database import Database
from cyberforge.persistence.models import Base, EmailMaterial


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture
def email_env(scenario_env):
    env = scenario_env
    env.emails = EmailMaterialService(env.service, create_gateway(), demo=True)
    env.token = env.tokens["teacher"]
    env.scenario = env.service.create(
        env.token, dict(topic="Синтетичне навчання", difficulty="beginner")
    )
    env.workspace = env.emails.load(env.token, env.scenario)
    return env


def generate(env, workspace=None, **kwargs):
    return env.emails.generate(env.token, workspace or env.workspace, **kwargs)


def snapshot(env):
    with env.database.engine.connect() as db:
        return db.execute(
            text("SELECT * FROM email_materials ORDER BY version_id")
        ).all()


def test_explicit_save_reopen_and_full_envelope(email_env):
    env = email_env
    assert env.workspace.state == MaterialState.EMPTY
    draft = generate(env)
    assert snapshot(env) == []
    saved = env.emails.save(env.token, env.workspace, draft)
    assert saved.state == MaterialState.SAVED and saved.revision == 1
    assert env.emails.load(env.token, env.scenario) == saved
    with env.database.sessions() as db:
        row = db.scalar(select(EmailMaterial))
        assert EmailDraftV2.model_validate_json(json.dumps(row.payload)) == draft
        assert row.context == synthetic_context(env.scenario).model_dump(mode="json")
        assert row.source_digest == draft.provenance.source_digest
        assert row.scenario_revision == env.scenario.revision
    database = Database(Path(env.database.engine.url.database))
    try:
        from cyberforge.application.accounts import AccountService

        accounts = AccountService(database)
        token = accounts.login("teacher", env.password)
        other = EmailMaterialService(ScenarioService(accounts), create_gateway())
        assert other.load(token, env.scenario) == saved
    finally:
        database.close()


def test_refinement_keeps_context_and_saved_content_until_save(email_env):
    env = email_env
    original = generate(env)
    saved = env.emails.save(env.token, env.workspace, original)
    before = snapshot(env)
    candidate = generate(env, saved, previous=saved.draft, refinement="Скороти текст")
    assert candidate != original
    assert candidate.provenance == original.provenance
    assert candidate.artifact.context == original.artifact.context
    assert candidate.slots.context_token != original.slots.context_token
    assert snapshot(env) == before
    updated = env.emails.save(env.token, saved, candidate)
    assert updated.revision == 2
    assert env.emails.load(env.token, env.scenario).draft == candidate
    assert env.service.get(env.token, env.scenario.id) == env.scenario


@pytest.mark.parametrize(
    "actor", ["other", "admin", "learner", "guest", "invalid", "revoked"]
)
def test_forbidden_writes_never_change_database(email_env, actor):
    env = email_env
    draft = generate(env)
    token = env.tokens.get(actor)
    if actor == "invalid":
        token = "not-a-session"
    elif actor == "revoked":
        token = env.accounts.login("teacher", env.password)
        env.accounts.logout(token)
    before = snapshot(env)
    with pytest.raises(AccessDenied):
        env.emails.generate(token, env.workspace)
    with pytest.raises(AccessDenied):
        env.emails.save(token, env.workspace, draft)
    if actor == "admin":
        assert env.emails.load(token, env.scenario).state == MaterialState.EMPTY
    else:
        with pytest.raises(AccessDenied):
            env.emails.load(token, env.scenario)
    assert snapshot(env) == before


def test_admin_can_write_only_own_scenarios(email_env):
    env = email_env
    token = env.tokens["admin"]
    scenario = env.service.create(
        token, dict(topic="Навчання адміністратора", difficulty="beginner")
    )
    workspace = env.emails.load(token, scenario)
    draft = env.emails.generate(token, workspace)
    assert env.emails.save(token, workspace, draft).state == MaterialState.SAVED


@pytest.mark.parametrize(
    "change", ["id", "version", "parameters", "missing", "digest", "context", "unsafe"]
)
def test_substitution_and_bad_provenance_fail_closed(email_env, change):
    env = email_env
    draft = generate(env)
    if change == "id":
        draft = draft.model_copy(update={"scenario_id": env.scenario.id + 1})
    elif change == "version":
        draft = draft.model_copy(update={"scenario_version": 2})
    elif change == "parameters":
        draft = draft.model_copy(
            update={
                "parameters": draft.parameters.model_copy(update={"topic": "Інша тема"})
            }
        )
    elif change == "missing":
        draft = draft.model_copy(update={"provenance": None})
    elif change == "digest":
        draft = draft.model_copy(
            update={
                "provenance": draft.provenance.model_copy(
                    update={"source_digest": "0" * 64}
                )
            }
        )
    elif change == "context":
        draft = draft.model_copy(
            update={
                "artifact": draft.artifact.model_copy(
                    update={
                        "context": draft.artifact.context.model_copy(
                            update={"organization": "Інша навчальна організація"}
                        )
                    }
                )
            }
        )
    else:
        draft.slots.background[0] = draft.slots.main.model_copy(
            update={"body_text": "<script>unsafe</script>"}
        )
    with pytest.raises(ApplicationError):
        env.emails.save(env.token, env.workspace, draft)
    with pytest.raises((ApplicationError, GenerationError)):
        generate(env, previous=draft, refinement="Уточни")
    assert snapshot(env) == []


def test_trusted_persisted_parameters_override_caller_fields(email_env):
    env = email_env
    forged = replace(
        env.workspace,
        scenario=env.scenario.model_copy(
            update={
                "parameters": env.scenario.parameters.model_copy(
                    update={"topic": "Підміна"}
                )
            }
        ),
    )
    draft = generate(env, forged)
    assert draft.parameters == env.scenario.parameters


def test_parameter_revision_invalidates_material_without_losing_it(email_env):
    env = email_env
    draft = generate(env)
    env.emails.save(env.token, env.workspace, draft)
    before = snapshot(env)
    updated = env.service.update(
        env.token,
        env.scenario.id,
        env.scenario.parameters.model_dump()
        | {"topic": "Оновлений синтетичний контекст"},
        expected_version=1,
        expected_revision=1,
    )
    stale = env.emails.load(env.token, updated)
    assert stale.state == MaterialState.REVIEW and stale.draft is None
    assert snapshot(env) == before
    with pytest.raises(ApplicationError):
        env.emails.save(env.token, env.workspace, draft)
    with pytest.raises(ApplicationError):
        env.emails.save(env.token, stale, draft)
    fresh = generate(env, stale)
    assert fresh.artifact.context == draft.artifact.context
    assert env.emails.save(env.token, stale, fresh).state == MaterialState.SAVED


@pytest.mark.parametrize(
    "column,value",
    [
        ("payload", "{broken"),
        ("payload", "{}"),
        ("payload", "null"),
        ("context", "{}"),
        ("source_digest", "0" * 64),
    ],
)
def test_corrupt_saved_payload_is_reviewable_and_repairable(email_env, column, value):
    env = email_env
    env.emails.save(env.token, env.workspace, generate(env))
    with env.database.engine.begin() as db:
        db.execute(
            text(f"UPDATE email_materials SET {column}=:value, revision=revision+1"),
            {"value": value},
        )
    before = snapshot(env)
    stale = env.emails.load(env.token, env.scenario)
    assert stale.state == MaterialState.REVIEW and stale.draft is None
    assert snapshot(env) == before
    assert env.emails.save(env.token, stale, generate(env, stale)).revision == 3


def test_failed_update_rolls_back_and_keeps_previous_artifact(email_env):
    env = email_env
    saved = env.emails.save(env.token, env.workspace, generate(env))
    candidate = generate(env, saved, previous=saved.draft, refinement="Уточни")
    before = snapshot(env)
    with env.database.engine.begin() as db:
        db.execute(
            text(
                "CREATE TRIGGER synthetic_email_failure BEFORE UPDATE "
                "ON email_materials BEGIN "
                "SELECT RAISE(ABORT, 'private SQL details'); END"
            )
        )
    with pytest.raises(ApplicationError) as failure:
        env.emails.save(env.token, saved, candidate)
    assert "private" not in str(failure.value)
    assert snapshot(env) == before
    assert env.emails.load(env.token, env.scenario) == saved


def test_archive_and_archive_restore_aba_reject_stale_editor(email_env):
    env = email_env
    draft = generate(env)
    saved = env.emails.save(env.token, env.workspace, draft)
    archived = env.service.archive(
        env.token,
        env.scenario.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=0,
    )
    before = snapshot(env)
    for workspace in (saved, env.emails.load(env.token, archived)):
        with pytest.raises(ApplicationError):
            env.emails.save(env.token, workspace, draft)
        with pytest.raises(ApplicationError):
            generate(env, workspace)
    restored = env.service.restore(
        env.token,
        env.scenario.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=1,
    )
    with pytest.raises(ApplicationError):
        env.emails.save(env.token, saved, draft)
    assert env.emails.load(env.token, restored).state == MaterialState.SAVED
    assert snapshot(env) == before


@pytest.mark.parametrize(
    "operation",
    [
        "UPDATE email_materials SET revision=revision+1",
        "DELETE FROM email_materials",
        "INSERT INTO email_materials SELECT * FROM email_materials",
    ],
)
@pytest.mark.parametrize("protected", ["published", "archived"])
def test_database_protects_material_independently_of_ui(
    email_env, operation, protected
):
    env = email_env
    saved = env.emails.save(env.token, env.workspace, generate(env))
    if protected == "published":
        with env.database.engine.begin() as db:
            db.execute(
                text(
                    "UPDATE scenario_versions SET status='published' "
                    "WHERE scenario_id=:id"
                ),
                {"id": env.scenario.id},
            )
    else:
        env.service.archive(
            env.token,
            env.scenario.id,
            expected_version=1,
            expected_revision=1,
            expected_archive_revision=0,
        )
    with pytest.raises(IntegrityError), env.database.engine.begin() as db:
        db.execute(text(operation))
    current = env.service.get(env.token, env.scenario.id)
    with pytest.raises(ApplicationError):
        env.emails.save(env.token, replace(saved, scenario=current), saved.draft)


def test_new_version_has_no_copied_material_and_preserves_history(email_env):
    env = email_env
    saved = env.emails.save(env.token, env.workspace, generate(env))
    with env.database.engine.begin() as db:
        db.execute(
            text(
                "UPDATE scenario_versions SET status='published' WHERE scenario_id=:id"
            ),
            {"id": env.scenario.id},
        )
    published = env.service.get(env.token, env.scenario.id)
    second = env.service.update(
        env.token,
        env.scenario.id,
        published.parameters.model_dump() | {"topic": "Нова навчальна версія"},
        expected_version=1,
        expected_revision=1,
    )
    assert env.emails.load(env.token, second).state == MaterialState.EMPTY
    assert env.emails.load(env.token, published).draft == saved.draft
    workspace = env.emails.load(env.token, second)
    with pytest.raises(ApplicationError):
        env.emails.save(env.token, workspace, saved.draft)
    assert (
        generate(env, workspace).artifact.context.internal_resource_id
        != saved.draft.slots.internal_resource_id
    )
    assert len(snapshot(env)) == 1


def test_independent_concurrent_editors_have_exactly_one_winner(email_env):
    env = email_env
    draft = generate(env)
    other_database = Database(Path(env.database.engine.url.database))
    from cyberforge.application.accounts import AccountService

    other_accounts = AccountService(other_database)
    other_token = other_accounts.login("teacher", env.password)
    other = EmailMaterialService(
        ScenarioService(other_accounts), create_gateway(), demo=True
    )
    barrier = Barrier(2)

    def save(service, token):
        barrier.wait(timeout=5)
        try:
            return service.save(token, env.workspace, draft).state
        except ApplicationError:
            return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(save, env.emails, env.token)
            second = pool.submit(save, other, other_token)
            assert sorted(
                [first.result(timeout=10), second.result(timeout=10)]
            ) == sorted([MaterialState.SAVED, "conflict"])
        assert len(snapshot(env)) == 1
        assert env.emails.load(env.token, env.scenario).revision == 1
    finally:
        other_database.close()


def test_upgrade_from_phase5_preserves_all_existing_records(email_env):
    env = email_env
    config = env.database.migration_config()
    with env.database.engine.begin() as db:
        config.attributes["connection"] = db
        command.downgrade(config, "0003_scenario_archive")
    before = env.service.get(env.token, env.scenario.id)
    env.database.upgrade()
    assert env.service.get(env.token, env.scenario.id) == before
    with env.database.engine.connect() as db:
        context = MigrationContext.configure(db)
        assert context.get_current_revision() == "0004_email_materials"
        assert compare_metadata(context, Base.metadata) == []
        assert db.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    env.emails.save(env.token, env.workspace, generate(env))
    with pytest.raises(RuntimeError), env.database.engine.begin() as db:
        config.attributes["connection"] = db
        command.downgrade(config, "0003_scenario_archive")
    assert len(snapshot(env)) == 1


class ScriptedService(EmailMaterialService):
    @property
    def available(self):
        return True


@pytest.mark.parametrize("result", ["valid", "invalid", "safety", "timeout", "quota"])
def test_real_agent_and_gateway_scripted_errors_preserve_saved(email_env, result):
    env = email_env
    saved = env.emails.save(env.token, env.workspace, generate(env))
    from cyberforge.application.email_demo import demo_gateway

    source = email_source(env.scenario, previous=saved.draft, refinement="Уточни")
    if result == "valid":
        gateway = demo_gateway(source)
        mock = gateway._providers[Provider.MOCK]
    else:
        response = (
            ProviderResponse(text="{}")
            if result == "invalid"
            else GenerationError(
                {
                    "safety": ErrorCategory.SAFETY,
                    "timeout": ErrorCategory.TIMEOUT,
                    "quota": ErrorCategory.BUDGET,
                }[result]
            )
        )
        mock = MockLLMProvider([response])
        gateway = LLMGateway(
            GatewayConfig(
                max_retries=0,
                limits={
                    key: RateLimits(tpm=1000000, tpd=1000000)
                    for key in ("mock", "mock:mock-v1")
                },
            ),
            {Provider.MOCK: mock},
        )
    service = ScriptedService(env.service, gateway)
    before = snapshot(env)
    if result == "valid":
        assert (
            service.generate(
                env.token, saved, previous=saved.draft, refinement="Уточни"
            ).provenance
            == saved.draft.provenance
        )
    else:
        with pytest.raises(GenerationError):
            service.generate(
                env.token, saved, previous=saved.draft, refinement="Уточни"
            )
    assert mock.calls == 1
    assert snapshot(env) == before


def test_unconfigured_mock_is_honest_unavailable(email_env):
    env = email_env
    service = EmailMaterialService(env.service, create_gateway())
    assert not service.available and "не налаштовано" in service.provider_label
    with pytest.raises(ApplicationError):
        service.generate(env.token, env.workspace)
    assert service.gateway._providers[Provider.MOCK].calls == 0


def test_expired_during_provider_execution_rejects_delivery(email_env, monkeypatch):
    env = email_env
    from cyberforge.application.email_demo import demo_gateway

    gateway = demo_gateway(email_source(env.scenario))
    mock = gateway._providers[Provider.MOCK]
    original = mock.generate

    def revoke(*args):
        env.accounts.logout(env.token)
        return original(*args)

    monkeypatch.setattr(mock, "generate", revoke)
    with pytest.raises(AccessDenied):
        ScriptedService(env.service, gateway).generate(env.token, env.workspace)
    assert snapshot(env) == []


@pytest.mark.parametrize(
    "provider,model",
    [(Provider.GROQ, "openai/gpt-oss-120b"), (Provider.GEMINI, "gemini-4-hydrogen")],
)
def test_configured_cloud_routing_uses_gateway_without_sdk_or_network(
    email_env, provider, model
):
    env = email_env
    from cyberforge.application.email_demo import demo_gateway

    scripted = demo_gateway(email_source(env.scenario))
    mock = scripted._providers[Provider.MOCK]
    requests = []
    original = mock.generate

    def record(request, schema):
        requests.append(request)
        return original(request, schema)

    mock.generate = record
    gateway = LLMGateway(
        GatewayConfig(
            provider=provider,
            model=model,
            max_retries=0,
            limits={
                key: RateLimits(tpm=1000000, tpd=1000000)
                for key in (provider.value, f"{provider.value}:{model}")
            },
        ),
        {provider: mock},
    )
    service = EmailMaterialService(env.service, gateway)
    assert provider.value in service.provider_label and model in service.provider_label
    draft = service.generate(env.token, env.workspace)
    assert mock.calls == 1 and len(requests) == 1
    assert requests[0].provider == provider and requests[0].model == model
    assert env.token not in requests[0].prompt
    assert env.password not in requests[0].prompt
    assert draft.provenance is not None and snapshot(env) == []
