"""Offline Phase 9 lifecycle, access, ordering, race and integrity regressions."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from cyberforge.application.learner_attempts import (
    AttemptEventService,
    LearnerAttemptService,
)
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.learning.contracts import AttemptEventV1, ScenarioAttemptV1
from cyberforge.persistence.models import Base
from tests.test_scenario_integration import publication_env, publish  # noqa: F401


@pytest.fixture
def learning_env(publication_env, monkeypatch):  # noqa: F811
    e = publication_env
    from cyberforge.application.learner_demo import demo_web_actions

    original_generate = e.webs.generate
    monkeypatch.setattr(
        e.webs,
        "generate",
        lambda *args, **kwargs: demo_web_actions(original_generate(*args, **kwargs)),
    )
    e.publication = publish(e)
    e.attempts = LearnerAttemptService(e.access)
    e.events = AttemptEventService(e.attempts)
    e.learner = e.tokens["learner"]
    return e


def start(e):
    return e.attempts.start_or_resume(e.learner, e.scenario.id)


def act(e, attempt, surface, action, **kwargs):
    return e.events.record(
        e.learner,
        attempt.attempt_id,
        request_id=kwargs.pop("request_id", uuid4()),
        expected_revision=attempt.revision,
        surface=surface,
        action_id=action,
        **kwargs,
    )


def enter_web(e, a):
    a = act(e, a, "email", "email_opened")
    return act(
        e,
        a,
        "transition",
        "open_internal",
        navigation=e.access.resolve_internal(e.learner, a.publication_id),
        source_message_identifier="main",
    )


def test_safe_decline_complete_repeat_and_contract_roundtrip(learning_env):
    e = learning_env
    a = start(e)
    assert a == start(e)
    assert ScenarioAttemptV1.model_validate_json(a.model_dump_json()) == a
    for action in ("email_opened", "inspect_sender", "inspect_link", "report"):
        a = act(e, a, "email", action)
    assert a.status == "IN_PROGRESS"
    a = act(e, a, "transition", "decline")
    assert e.attempts.get(e.learner, a.attempt_id).status == "IN_PROGRESS"
    request = uuid4()
    completed = act(e, a, "system", "completed", request_id=request)
    assert completed.status == "COMPLETED" and not completed.web_visited
    assert act(e, a, "system", "completed", request_id=request) == completed
    with pytest.raises(ApplicationError):
        act(e, completed, "email", "report")
    events = e.attempts.events(e.learner, a.attempt_id)
    assert [x.sequence for x in events] == list(range(1, len(events) + 1))
    assert [x.action_id for x in events] == [
        "started",
        "email_opened",
        "inspect_sender",
        "inspect_link",
        "report",
        "decline",
        "completed",
    ]
    assert all(
        AttemptEventV1.model_validate_json(x.model_dump_json()) == x for x in events
    )
    assert start(e).attempt_id != a.attempt_id
    assert len(e.attempts.history(e.learner)) == 2


def test_web_requires_successful_display_and_component_pairs(learning_env):
    e = learning_env
    a = enter_web(e, start(e))
    assert a.current_stage == "WEB" and not a.web_visited
    with pytest.raises(ApplicationError):
        act(e, a, "system", "completed")
    _, state = e.attempts.content(e.learner, a.attempt_id)
    pairs = [
        (c.id, action.id)
        for c in state.web.page.components
        for action in getattr(c, "actions", ())
    ]
    component, action = pairs[0]
    with pytest.raises(ApplicationError):
        act(e, a, "web", action, component_id=component)
    a = act(e, a, "system", "web_entered")
    with pytest.raises(ApplicationError):
        act(e, a, "web", action, component_id="forged")
    for component, action in pairs:
        a = act(e, a, "web", action, component_id=component)
    a = act(e, a, "system", "completed")
    assert a.web_visited and a.status == "COMPLETED"


@pytest.mark.parametrize("role", ["teacher", "other", "admin", None])
def test_forbidden_roles_and_sessions(learning_env, role):
    e = learning_env
    a = start(e)
    token = e.tokens[role] if role else None
    for read in (
        lambda: e.attempts.history(token),
        lambda: e.attempts.get(token, a.attempt_id),
        lambda: e.attempts.events(token, a.attempt_id),
        lambda: e.attempts.content(token, a.attempt_id),
        lambda: e.attempts.start_or_resume(token, e.scenario.id),
        lambda: e.events.record(
            token,
            a.attempt_id,
            request_id=uuid4(),
            expected_revision=a.revision,
            surface="email",
            action_id="email_opened",
        ),
    ):
        with pytest.raises(ApplicationError):
            read()


def test_cross_learner_history_and_events_denied(learning_env):
    e = learning_env
    a = start(e)
    e.accounts.create_user(
        e.tokens["admin"], "second", "Другий", Role.LEARNER, e.password
    )
    other = e.accounts.login("second", e.password)
    assert not e.attempts.history(other)
    for method in (e.attempts.get, e.attempts.events, e.attempts.content):
        with pytest.raises(ApplicationError):
            method(other, a.attempt_id)


@pytest.mark.parametrize("kind", ["grant", "membership", "archive", "account"])
def test_revocation_preserves_history_and_restored_resume(learning_env, kind):
    e = learning_env
    a = enter_web(e, start(e))
    actor = e.tokens["admin"]
    if kind == "grant":
        e.publications.change_grant(
            e.token, a.publication_id, e.group.id, active=False, expected_revision=1
        )
    elif kind == "membership":
        e.groups.save_group(
            actor,
            e.group.name,
            group_id=e.group.id,
            instructors=(e.teacher_id,),
            learners=(),
        )
    elif kind == "archive":
        e.scenario = e.service.archive(
            e.token,
            e.scenario.id,
            expected_version=e.scenario.version,
            expected_revision=e.scenario.revision,
            expected_archive_revision=e.scenario.archive_revision,
        )
    else:
        e.accounts.update_user(actor, e.learner_id, "learner", Role.LEARNER, False)
    with pytest.raises(ApplicationError):
        act(e, a, "system", "web_entered")
    with pytest.raises(ApplicationError):
        e.attempts.content(e.learner, a.attempt_id)
    if kind != "account":
        assert e.attempts.history(e.learner)[0] == a
        assert not e.attempts.catalog(e.learner)[0].available
    if kind == "grant":
        e.publications.change_grant(
            e.token, a.publication_id, e.group.id, active=True, expected_revision=2
        )
    elif kind == "membership":
        e.groups.save_group(
            actor,
            e.group.name,
            group_id=e.group.id,
            instructors=(e.teacher_id,),
            learners=(e.learner_id,),
        )
    elif kind == "archive":
        e.service.restore(
            e.token,
            e.scenario.id,
            expected_version=e.scenario.version,
            expected_revision=e.scenario.revision,
            expected_archive_revision=e.scenario.archive_revision,
        )
    else:
        e.accounts.update_user(actor, e.learner_id, "learner", Role.LEARNER, True)
        e.learner = e.accounts.login("learner", e.password)
    assert start(e) == a
    assert act(e, a, "system", "web_entered").web_visited


def test_idempotency_repeated_actions_stale_revision_and_privacy(learning_env):
    e = learning_env
    a = act(e, start(e), "email", "email_opened")
    request = uuid4()
    b = act(e, a, "email", "inspect_link", request_id=request)
    assert act(e, a, "email", "inspect_link", request_id=request) == b
    with pytest.raises(ApplicationError):
        act(e, b, "email", "report", request_id=request)
    with pytest.raises(ApplicationError):
        act(e, a, "email", "report")
    c = act(e, b, "email", "inspect_link")
    assert c.last_event_sequence == b.last_event_sequence + 1
    with pytest.raises(TypeError):
        act(e, c, "email", "report", metadata={"password": "secret"})
    assert "secret" not in str(e.attempts.events(e.learner, a.attempt_id))


def test_concurrent_start_and_concurrent_event(learning_env):
    e = learning_env
    with ThreadPoolExecutor(max_workers=4) as pool:
        attempts = tuple(pool.map(lambda _: start(e), range(4)))
    assert len({a.attempt_id for a in attempts}) == 1
    a = attempts[0]
    request = uuid4()
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = tuple(
            pool.map(
                lambda _: act(e, a, "email", "email_opened", request_id=request),
                range(4),
            )
        )
    assert len({v.last_event_sequence for v in values}) == 1
    assert len(e.attempts.events(e.learner, a.attempt_id)) == 2


def test_abandonment_explicit_terminal_and_new_start(learning_env):
    e = learning_env
    a = start(e)
    assert start(e).status == "IN_PROGRESS"
    b = act(e, a, "system", "abandoned")
    assert b.abandoned_at is not None and b.status == "ABANDONED"
    with pytest.raises(ApplicationError):
        act(e, b, "email", "email_opened")
    assert start(e).attempt_id != b.attempt_id


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE attempt_events SET action_id='report'",
        "DELETE FROM attempt_events",
        "DELETE FROM scenario_attempts",
        (
            "UPDATE scenario_attempts SET manifest_digest='forged', "
            "revision=revision+1, last_event_sequence=last_event_sequence+1"
        ),
    ],
)
def test_direct_history_mutation_rejected(learning_env, statement):
    e = learning_env
    start(e)
    with pytest.raises(IntegrityError), e.database.engine.begin() as db:
        db.execute(text(statement))


def test_downgrade_guard_metadata_and_rollback(learning_env):
    e = learning_env
    with e.database.engine.connect() as connection:
        assert not compare_metadata(
            MigrationContext.configure(connection), Base.metadata
        )
    a = start(e)
    config = e.database.migration_config()
    with pytest.raises(RuntimeError), e.database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0006_scenario_integration_publication")
    assert e.attempts.get(e.learner, a.attempt_id) == a


def test_active_old_version_overrides_latest_and_revoked_old_blocks(learning_env):
    e = learning_env
    a = start(e)
    old = e.publication
    e.scenario = e.service.create_next_draft(
        e.token, e.service.get(e.token, e.scenario.id)
    )
    latest = publish(e)
    assert latest.id != old.id
    assert e.access.catalog(e.learner)[0].id == latest.id
    assert e.attempts.catalog(e.learner)[0].publication_id == old.id
    assert start(e) == a
    e.publications.change_grant(
        e.token, old.id, e.group.id, active=False, expected_revision=1
    )
    assert not e.attempts.catalog(e.learner)[0].available
    with pytest.raises(ApplicationError):
        start(e)
    assert e.attempts.history(e.learner)[0].publication_id == old.id
    e.publications.change_grant(
        e.token, old.id, e.group.id, active=True, expected_revision=2
    )
    a = act(e, a, "system", "abandoned")
    assert start(e).publication_id == latest.id


def test_alternative_group_access_and_catalog_deduplication(learning_env):
    e = learning_env
    a = start(e)
    group = e.groups.save_group(
        e.tokens["admin"],
        "Альтернативна",
        instructors=(e.teacher_id,),
        learners=(e.learner_id,),
    )
    e.publications.change_grant(
        e.token, a.publication_id, group.id, active=True, expected_revision=0
    )
    e.publications.change_grant(
        e.token, a.publication_id, e.group.id, active=False, expected_revision=1
    )
    assert len(e.attempts.catalog(e.learner)) == 1
    assert start(e) == a
    assert act(e, a, "email", "email_opened").email_opened
    assert a.authorization_group_id == e.group.id  # provenance does not confer access


@pytest.mark.parametrize(
    "field,value",
    [
        ("publication_id", 999),
        ("scenario_id", 999),
        ("scenario_version", 99),
        ("manifest_digest", "a" * 64),
        ("internal_resource_id", "forged_resource"),
    ],
)
def test_forged_navigation_denied_atomically(learning_env, field, value):
    e = learning_env
    a = act(e, start(e), "email", "email_opened")
    nav = e.access.resolve_internal(e.learner, a.publication_id)
    nav = nav.model_copy(update={field: value})
    with pytest.raises(ApplicationError):
        act(
            e,
            a,
            "transition",
            "open_internal",
            navigation=nav,
            source_message_identifier="main",
        )
    assert e.attempts.get(e.learner, a.attempt_id) == a


def test_wrong_source_stage_unknown_actions_and_completion_denied(learning_env):
    e = learning_env
    a = start(e)
    for surface, action in (
        ("email", "inspect_sender"),
        ("system", "completed"),
        ("transition", "decline"),
        ("system", "web_entered"),
        ("email", "submit_synthetic"),
        ("email", "execute"),
    ):
        with pytest.raises(ApplicationError):
            act(e, a, surface, action)
    a = act(e, a, "email", "email_opened")
    with pytest.raises(ApplicationError):
        act(
            e,
            a,
            "transition",
            "open_internal",
            navigation=e.access.resolve_internal(e.learner, a.publication_id),
            source_message_identifier="background",
        )
    a = act(
        e,
        a,
        "transition",
        "open_internal",
        navigation=e.access.resolve_internal(e.learner, a.publication_id),
        source_message_identifier="main",
    )
    with pytest.raises(ApplicationError):
        act(e, a, "email", "report")


def test_failed_event_insert_rolls_back_terminal_state(learning_env):
    e = learning_env
    a = act(e, act(e, start(e), "email", "email_opened"), "transition", "decline")
    with e.database.engine.begin() as db:
        db.exec_driver_sql(
            "CREATE TRIGGER reject_completion BEFORE INSERT ON "
            "attempt_events WHEN NEW.action_id='completed' BEGIN SELECT "
            "RAISE(ABORT,'test failure'); END"
        )
    with pytest.raises(ApplicationError):
        act(e, a, "system", "completed")
    assert e.attempts.get(e.learner, a.attempt_id) == a
    assert e.attempts.events(e.learner, a.attempt_id)[-1].action_id == "decline"


def test_concurrent_distinct_events_require_fresh_revision(learning_env):
    e = learning_env
    a = act(e, start(e), "email", "email_opened")

    def record(action):
        try:
            return act(e, a, "email", action)
        except ApplicationError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = tuple(pool.map(record, ("inspect_sender", "inspect_link")))
    assert sum(v is not None for v in values) == 1
    assert (
        e.attempts.get(e.learner, a.attempt_id).last_event_sequence
        == a.last_event_sequence + 1
    )


def test_upgrade_existing_phase8_publication_and_empty_downgrade(learning_env):
    e = learning_env
    before = e.access.content(e.learner, e.publication.id)[0]
    config = e.database.migration_config()
    with e.database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0006_scenario_integration_publication")
    assert e.access.content(e.learner, e.publication.id)[0] == before
    e.database.upgrade()
    assert e.access.content(e.learner, e.publication.id)[0] == before
    assert start(e).publication_id == before.id


@pytest.mark.parametrize("web", [False, True])
def test_new_database_connection_and_reauthentication_resume(learning_env, web):
    from cyberforge.application.accounts import AccountService
    from cyberforge.application.email_materials import EmailMaterialService
    from cyberforge.application.scenario_integration import ScenarioIntegrationService
    from cyberforge.application.scenario_publication import (
        PublicationAccessService,
        ScenarioPublicationService,
    )
    from cyberforge.application.scenario_readiness import ScenarioReadinessService
    from cyberforge.application.scenarios import ScenarioService
    from cyberforge.application.web_materials import WebMaterialService
    from cyberforge.llm.factory import create_gateway
    from cyberforge.persistence.database import Database

    e = learning_env
    a = enter_web(e, start(e)) if web else start(e)
    old_events = e.attempts.events(e.learner, a.attempt_id)
    from pathlib import Path

    path = Path(e.database.engine.url.database)
    other_db = Database(path)
    try:
        other_db.upgrade()
        accounts = AccountService(other_db)
        token = accounts.login("learner", e.password)
        integration = ScenarioIntegrationService(
            WebMaterialService(
                EmailMaterialService(
                    ScenarioService(accounts), create_gateway(), demo=True
                ),
                demo=True,
            )
        )
        access = PublicationAccessService(
            ScenarioPublicationService(ScenarioReadinessService(integration))
        )
        attempts = LearnerAttemptService(access)
        assert attempts.start_or_resume(token, a.scenario_id) == a
        assert attempts.events(token, a.attempt_id) == old_events
        assert attempts.content(token, a.attempt_id)[0] == a
    finally:
        other_db.close()
