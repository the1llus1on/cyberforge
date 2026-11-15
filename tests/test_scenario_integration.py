"""Offline integration/publication security, integrity and concurrency gates."""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import (
    PublicationAccessService,
    ScenarioPublicationService,
)
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.groups.service import GroupService
from cyberforge.llm.factory import create_gateway
from cyberforge.persistence.models import Base
from cyberforge.scenario_integration.contracts import (
    RubricDefinitionV1,
    ScenarioPublicationManifestV1,
    criterion,
)


@pytest.fixture
def publication_env(scenario_env, monkeypatch):
    env = scenario_env

    def forbidden(*args, **kwargs):
        raise AssertionError("Phase8 must not connect to network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    env.token = env.tokens["teacher"]
    env.emails = EmailMaterialService(env.service, create_gateway(), demo=True)
    env.webs = WebMaterialService(env.emails, demo=True)
    env.integration = ScenarioIntegrationService(env.webs)
    env.readiness = ScenarioReadinessService(env.integration)
    env.publications = ScenarioPublicationService(env.readiness)
    env.access = PublicationAccessService(env.publications)
    env.groups = GroupService(env.accounts)
    env.teacher_id = env.accounts.current(env.token).id
    env.learner_id = env.accounts.current(env.tokens["learner"]).id
    env.group = env.groups.save_group(
        env.tokens["admin"],
        "Синтетична група",
        instructors=(env.teacher_id,),
        learners=(env.learner_id,),
    )
    env.other_group = env.groups.save_group(
        env.tokens["admin"],
        "Інша група",
        instructors=(env.accounts.current(env.tokens["other"]).id,),
        learners=(),
    )
    env.scenario = env.service.create(
        env.token, dict(topic="Навчальна інтеграція", difficulty="beginner")
    )
    return env


def materials(env):
    ew = env.emails.load(env.token, env.scenario)
    email = env.emails.generate(env.token, ew)
    env.saved_email = env.emails.save(env.token, ew, email)
    ww = env.webs.load(env.token, env.scenario)
    web = env.webs.generate(env.token, ww)
    env.saved_web = env.webs.save(env.token, ww, web)


def link(env, **overrides):
    state = env.integration.inspect(env.token, env.scenario)
    values = dict(
        link_label="Переглянути матеріал",
        display_url=state.web.page.display_url,
        target_resource_id=state.web.page.internal_resource_id,
        expected_revision=state.checked_sources["link_revision"] or 0,
        expected_email_revision=state.checked_sources["email_revision"],
        expected_web_revision=state.checked_sources["web_revision"],
    )
    return env.integration.save_link(env.token, env.scenario, **(values | overrides))


def ready(env):
    materials(env)
    link(env)
    env.rubric = env.integration.save_rubric(
        env.token,
        env.scenario,
        (
            criterion("email.sender"),
            criterion("transition.safe_decline"),
            criterion("web.address"),
        ),
        expected_revision=0,
    )
    return env.readiness.evaluate(
        env.token, env.scenario, selected_group_ids=(env.group.id,)
    )


def confirm(env, report=None):
    report = report or env.readiness.evaluate(
        env.token, env.scenario, selected_group_ids=(env.group.id,)
    )
    return env.readiness.confirm(
        env.token,
        env.scenario,
        review_fingerprint=report.review_fingerprint,
        selected_group_ids=report.selected_group_ids,
        acknowledged_warnings=report.acknowledgement_requirements,
        semantic_review=True,
    )


def publish(env):
    ready(env)
    receipt = confirm(env)
    return env.publications.publish(
        env.token, env.scenario, confirmation_id=receipt.confirmation_id
    )


def count(env, table):
    with env.database.engine.connect() as db:
        return db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_readiness_missing_sources_and_determinism(publication_env):
    e = publication_env
    report = e.readiness.evaluate(e.token, e.scenario)
    assert not report.technical_ready and not report.final_ready
    assert report == e.readiness.evaluate(e.token, e.scenario)
    assert report.snapshot is None and report.checked_sources["email_revision"] is None
    assert {c.check_id for c in report.checks if c.status == "BLOCKED"} >= {
        "email",
        "web",
        "link",
        "rubric",
        "groups",
        "instructor_confirmation",
    }
    for c in report.checks:
        assert c.explanation and c.correction
    with pytest.raises(ApplicationError):
        confirm(e, report)
    assert count(e, "publication_reviews") == 0


def test_atomic_publication_manifest_reopen_and_status_revision(publication_env):
    e = publication_env
    report = ready(e)
    assert report.technical_ready and not report.final_ready
    assert report == e.readiness.evaluate(
        e.token, e.scenario, selected_group_ids=(e.group.id,)
    )
    receipt = confirm(e, report)
    assert e.readiness.evaluate(
        e.token,
        e.scenario,
        selected_group_ids=(e.group.id,),
        confirmation_id=receipt.confirmation_id,
    ).final_ready
    pub = e.publications.publish(
        e.token, e.scenario, confirmation_id=receipt.confirmation_id
    )
    assert e.publications.history(e.token, e.scenario.id) == (pub,)
    assert e.access.catalog(e.tokens["learner"]) == (pub,)
    assert (
        e.access.resolve_internal(e.tokens["learner"], pub.id).internal_resource_id
        == e.saved_web.draft.page.internal_resource_id
    )
    assert e.access.content(e.tokens["learner"], pub.id)[1].email == e.saved_email.draft
    current = e.service.get(e.token, e.scenario.id)
    assert (current.status, current.revision) == ("published", e.scenario.revision)
    assert e.emails.load(e.token, current).draft == e.saved_email.draft
    assert e.webs.load(e.token, current).draft == e.saved_web.draft
    assert (
        ScenarioPublicationManifestV1.model_validate_json(
            pub.manifest.model_dump_json()
        )
        == pub.manifest
    )
    assert len(e.publications.audit(e.token, pub.id)) == 1
    with pytest.raises(ApplicationError):
        e.publications.publish(
            e.token, current, confirmation_id=receipt.confirmation_id
        )
    assert count(e, "scenario_publications") == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("display_url", "javascript:alert(1)"),
        ("display_url", "https://u:p@training.invalid"),
        ("display_url", "https://training.invalid/%0a"),
        ("link_label", "<a>"),
        ("target_resource_id", "forged_resource"),
        ("expected_email_revision", 99),
        ("expected_web_revision", 99),
        ("expected_revision", 99),
    ],
)
def test_unsafe_or_forged_link_denied(publication_env, field, value):
    e = publication_env
    materials(e)
    with pytest.raises(ApplicationError):
        link(e, **{field: value})
    assert count(e, "scenario_links") == 0


def test_display_mismatch_warns_without_mutating_artifacts(publication_env):
    e = publication_env
    ready(e)
    before = (
        e.saved_email.draft.model_dump_json(),
        e.saved_web.draft.model_dump_json(),
    )
    value = link(e, display_url="https://different.training.invalid/lesson")
    assert value.allowed_action == "open_internal"
    report = e.readiness.evaluate(e.token, e.scenario, selected_group_ids=(e.group.id,))
    assert (
        report.technical_ready
        and "display_url_mismatch" in report.acknowledgement_requirements
    )
    with pytest.raises(ApplicationError):
        e.readiness.confirm(
            e.token,
            e.scenario,
            review_fingerprint=report.review_fingerprint,
            selected_group_ids=(e.group.id,),
            acknowledged_warnings=("semantic_review",),
            semantic_review=True,
        )
    pub = e.publications.publish(
        e.token, e.scenario, confirmation_id=confirm(e).confirmation_id
    )
    assert pub.id and before == (
        e.emails.load(e.token, e.scenario).draft.model_dump_json(),
        e.webs.load(e.token, e.scenario).draft.model_dump_json(),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario_id", 999),
        ("scenario_version", 999),
        ("source_message_identifier", "background_1"),
        ("allowed_action", "navigate_external"),
        ("target_resource_id", "other_resource"),
        ("target_web_revision", 999),
        ("source_email_digest", "0" * 64),
        ("linkage_provenance", "0" * 64),
        ("revision", 999),
    ],
)
def test_revalidate_stored_link(publication_env, field, value):
    e = publication_env
    ready(e)
    with e.database.engine.begin() as db:
        payload = json.loads(
            db.exec_driver_sql("SELECT payload FROM scenario_links").scalar_one()
        )
        payload[field] = value
        db.execute(
            text("UPDATE scenario_links SET revision=revision+1,payload=:p"),
            {"p": json.dumps(payload)},
        )
    report = e.readiness.evaluate(e.token, e.scenario)
    assert not report.technical_ready
    assert next(c for c in report.checks if c.check_id == "link").status == "BLOCKED"


@pytest.mark.parametrize(
    "source", ["email", "web", "link", "rubric", "parameters", "archive", "assignment"]
)
def test_review_invalidated_by_change(publication_env, source):
    e = publication_env
    report = ready(e)
    receipt = confirm(e, report)
    if source == "email":
        e.emails.save(e.token, e.saved_email, e.saved_email.draft)
    elif source == "web":
        e.webs.save(e.token, e.saved_web, e.saved_web.draft)
    elif source == "link":
        link(e, link_label="Інша назва")
    elif source == "rubric":
        e.integration.save_rubric(
            e.token, e.scenario, (criterion("email.sender", 2.0),), expected_revision=1
        )
    elif source == "parameters":
        e.service.update(
            e.token,
            e.scenario.id,
            e.scenario.parameters.model_dump() | {"topic": "Змінено"},
            expected_version=1,
            expected_revision=1,
        )
    elif source == "archive":
        e.service.archive(
            e.token,
            e.scenario.id,
            expected_version=1,
            expected_revision=1,
            expected_archive_revision=0,
        )
    else:
        e.groups.set_members(e.tokens["admin"], e.group.id, (), (e.learner_id,))
    with pytest.raises(ApplicationError):
        e.publications.publish(
            e.token, e.scenario, confirmation_id=receipt.confirmation_id
        )
    assert (
        count(e, "scenario_publications")
        == count(e, "publication_groups")
        == count(e, "publication_grant_audit")
        == 0
    )


@pytest.mark.parametrize("who", ["other", "learner", "admin"])
def test_forbidden_owner_writes_and_review(publication_env, who):
    e = publication_env
    ready(e)
    receipt = confirm(e)
    token = e.tokens[who]
    for operation in (
        lambda: e.readiness.confirm(
            token,
            e.scenario,
            review_fingerprint=receipt.review_fingerprint,
            selected_group_ids=(e.group.id,),
            acknowledged_warnings=receipt.acknowledged_warnings,
            semantic_review=True,
        ),
        lambda: e.publications.publish(
            token, e.scenario, confirmation_id=receipt.confirmation_id
        ),
        lambda: e.integration.save_rubric(
            token, e.scenario, (criterion("email.sender"),), expected_revision=1
        ),
    ):
        with pytest.raises(ApplicationError):
            operation()
    assert count(e, "scenario_publications") == 0


@pytest.mark.parametrize("groups", [(), (99999,), (True,), (1, 1)])
def test_invalid_groups_cannot_publish(publication_env, groups):
    e = publication_env
    ready(e)
    with pytest.raises(ApplicationError):
        report = e.readiness.evaluate(e.token, e.scenario, selected_group_ids=groups)
        confirm(e, report)
    assert count(e, "scenario_publications") == 0


def test_unauthorized_groups_denied(publication_env):
    e = publication_env
    ready(e)
    report = e.readiness.evaluate(
        e.token, e.scenario, selected_group_ids=(e.other_group.id,)
    )
    assert report.technical_ready and not report.final_ready
    with pytest.raises(ApplicationError):
        confirm(e, report)


def test_concurrent_publication_one_winner(publication_env):
    e = publication_env
    ready(e)
    receipt = confirm(e)
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=5)
        try:
            return e.publications.publish(
                e.token, e.scenario, confirmation_id=receipt.confirmation_id
            ).id
        except ApplicationError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert sum(r is not None for r in results) == 1
    assert (
        count(e, "scenario_publications")
        == count(e, "publication_groups")
        == count(e, "publication_grant_audit")
        == 1
    )


def test_forced_rollback_has_no_partial_publication(publication_env):
    e = publication_env
    ready(e)
    receipt = confirm(e)

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE scenario_versions SET status"):
            raise RuntimeError("forced final transaction failure")

    event.listen(e.database.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            e.publications.publish(
                e.token, e.scenario, confirmation_id=receipt.confirmation_id
            )
    finally:
        event.remove(e.database.engine, "before_cursor_execute", fail)
    assert (
        count(e, "scenario_publications")
        == count(e, "publication_groups")
        == count(e, "publication_grant_audit")
        == 0
    )
    assert e.service.get(e.token, e.scenario.id).status == "draft"
    assert e.publications.publish(
        e.token, e.scenario, confirmation_id=receipt.confirmation_id
    ).id


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE scenario_versions SET parameters='{}'",
        "UPDATE scenario_versions SET status='draft'",
        "DELETE FROM scenario_versions",
        "UPDATE email_materials SET revision=revision+1",
        "DELETE FROM email_materials",
        "UPDATE web_materials SET revision=revision+1",
        "DELETE FROM web_materials",
        "UPDATE scenario_links SET revision=revision+1",
        "DELETE FROM scenario_links",
        "UPDATE rubric_definitions SET revision=revision+1",
        "DELETE FROM rubric_definitions",
        "UPDATE scenario_publications SET manifest='{}'",
        "DELETE FROM scenario_publications",
        "DELETE FROM publication_reviews",
        "UPDATE publication_reviews SET payload='{}'",
        "DELETE FROM publication_grant_audit",
        "UPDATE publication_grant_audit SET operation='revoke'",
        "DELETE FROM publication_groups",
        "INSERT OR REPLACE INTO scenario_versions SELECT * FROM scenario_versions",
        "INSERT OR REPLACE INTO scenario_publications "
        "SELECT * FROM scenario_publications",
        "INSERT OR REPLACE INTO publication_reviews SELECT * FROM publication_reviews",
        "INSERT OR REPLACE INTO publication_grant_audit "
        "SELECT * FROM publication_grant_audit",
        "INSERT OR REPLACE INTO scenarios SELECT * FROM scenarios",
        "INSERT OR REPLACE INTO email_materials SELECT * FROM email_materials",
        "INSERT OR REPLACE INTO web_materials SELECT * FROM web_materials",
        "INSERT OR REPLACE INTO rubric_definitions SELECT * FROM rubric_definitions",
        "INSERT OR REPLACE INTO scenario_links SELECT * FROM scenario_links",
    ],
)
def test_direct_sql_cannot_mutate_published_sources(publication_env, sql):
    e = publication_env
    pub = publish(e)
    with pytest.raises(IntegrityError), e.database.engine.begin() as db:
        db.exec_driver_sql(sql)
    assert e.publications.history(e.token, e.scenario.id) == (pub,)


def test_grants_audit_membership_archive_and_new_draft(publication_env):
    e = publication_env
    pub = publish(e)
    second = e.groups.save_group(
        e.tokens["admin"],
        "Друга",
        instructors=(e.teacher_id,),
        learners=(e.learner_id,),
    )
    e.publications.change_grant(
        e.token, pub.id, second.id, active=True, expected_revision=0
    )
    assert e.access.catalog(e.tokens["learner"]) == (pub,)
    assert len(e.publications.audit(e.token, pub.id)) == 2
    with pytest.raises(ApplicationError):
        e.publications.change_grant(
            e.token, pub.id, e.other_group.id, active=True, expected_revision=0
        )
    with pytest.raises(ApplicationError):
        e.publications.change_grant(
            e.tokens["other"], pub.id, second.id, active=False, expected_revision=1
        )
    e.groups.set_members(e.tokens["admin"], e.group.id, (), (e.learner_id,))
    e.publications.change_grant(
        e.token, pub.id, e.group.id, active=False, expected_revision=1
    )
    with pytest.raises(ApplicationError):
        e.publications.change_grant(
            e.token, pub.id, e.group.id, active=True, expected_revision=2
        )
    e.publications.change_grant(
        e.token, pub.id, second.id, active=False, expected_revision=1
    )
    assert e.access.catalog(e.tokens["learner"]) == ()
    with pytest.raises(ApplicationError):
        e.access.resolve_internal(e.tokens["learner"], pub.id)
    e.publications.change_grant(
        e.token, pub.id, second.id, active=True, expected_revision=2
    )
    events = e.publications.audit(e.token, pub.id)
    assert [a.operation for a in events] == [
        "grant",
        "grant",
        "revoke",
        "revoke",
        "grant",
    ]
    assert e.publications.history(e.token, e.scenario.id) == (pub,)
    archived = e.service.archive(
        e.token,
        e.scenario.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=0,
    )
    assert e.access.catalog(e.tokens["learner"]) == ()
    assert e.publications.audit(e.token, pub.id) == events
    restored = e.service.restore(
        e.token,
        e.scenario.id,
        expected_version=1,
        expected_revision=1,
        expected_archive_revision=archived.archive_revision,
    )
    assert e.access.catalog(e.tokens["learner"]) == (pub,)
    assert e.access.resolve_internal(e.tokens["learner"], pub.id)
    draft = e.service.create_next_draft(e.token, restored)
    assert (
        draft.version == 2
        and draft.status == "draft"
        and draft.parameters == restored.parameters
    )
    assert e.integration.inspect(e.token, draft).link is None
    assert e.integration.inspect(e.token, draft).rubric is None
    assert (
        e.emails.load(e.token, draft).draft is None
        and e.webs.load(e.token, draft).draft is None
    )
    assert e.publications.history(e.token, e.scenario.id) == (pub,)
    assert e.access.catalog(e.tokens["learner"]) == (pub,)
    with pytest.raises(ApplicationError):
        e.service.create_next_draft(e.token, restored)


def test_latest_eligible_version_resolution(publication_env):
    e = publication_env
    first = publish(e)
    e.scenario = e.service.create_next_draft(
        e.token, e.service.get(e.token, e.scenario.id)
    )
    second = publish(e)
    assert e.access.catalog(e.tokens["learner"]) == (second,)
    assert e.access.content(e.tokens["learner"], first.id)[0] == first
    e.publications.change_grant(
        e.token, second.id, e.group.id, active=False, expected_revision=1
    )
    assert e.access.catalog(e.tokens["learner"]) == (first,)
    e.groups.set_members(e.tokens["admin"], e.group.id, (e.teacher_id,), ())
    assert e.access.catalog(e.tokens["learner"]) == ()


def test_migration_metadata_preservation_and_safe_downgrade(publication_env):
    e = publication_env
    materials(e)
    before = e.saved_email.draft.model_dump_json(), e.saved_web.draft.model_dump_json()
    config = e.database.migration_config()
    with e.database.engine.begin() as db:
        config.attributes["connection"] = db
        command.downgrade(config, "0005_web_materials")
    e.database.upgrade()
    assert before == (
        e.emails.load(e.token, e.scenario).draft.model_dump_json(),
        e.webs.load(e.token, e.scenario).draft.model_dump_json(),
    )
    with e.database.engine.connect() as db:
        context = MigrationContext.configure(db)
        assert context.get_current_revision() == "0006_scenario_integration_publication"
        assert compare_metadata(context, Base.metadata) == []
        assert db.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert db.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    link(e)
    with pytest.raises(RuntimeError), e.database.engine.begin() as db:
        config.attributes["connection"] = db
        command.downgrade(config, "0005_web_materials")
    assert count(e, "scenario_links") == 1


@pytest.mark.parametrize(
    "change",
    [
        "empty",
        "duplicate",
        "weight_zero",
        "weight_nan",
        "unknown",
        "action",
        "applicability",
        "web_only",
    ],
)
def test_rubric_validation_and_safe_no_web_path(publication_env, change):
    e = publication_env
    criteria = [
        criterion("email.sender"),
        criterion("transition.safe_decline"),
        criterion("web.address"),
    ]
    payload = [c.model_dump(mode="json") for c in criteria]
    if change == "empty":
        payload = []
    elif change == "duplicate":
        payload.append(payload[0])
    elif change == "weight_zero":
        payload[0]["weight"] = 0
    elif change == "weight_nan":
        payload[0]["weight"] = float("nan")
    elif change == "unknown":
        payload[0]["criterion_id"] = "model.generated"
    elif change == "action":
        payload[0]["evidence_actions"] = ["eval"]
    elif change == "applicability":
        payload[2]["applicability"] = "all_attempts"
    else:
        payload = [payload[2]]
    # model_construct deliberately bypasses client-side checks; service must revalidate.
    from cyberforge.scenario_integration.contracts import RubricCriterionV1

    forged = tuple(RubricCriterionV1.model_construct(**p) for p in payload)
    with pytest.raises(ApplicationError):
        e.integration.save_rubric(e.token, e.scenario, forged, expected_revision=0)
    assert count(e, "rubric_definitions") == 0
    value = e.integration.save_rubric(
        e.token, e.scenario, tuple(criteria), expected_revision=0
    )
    assert RubricDefinitionV1.model_validate_json(value.model_dump_json()) == value
    assert value.criteria[2].applicability == "web_visited"
    assert criterion("transition.safe_decline", applicability="web_not_visited")


@pytest.mark.parametrize(
    "table,field,value,reason",
    [
        ("email_materials", "scenario_version", 99, "email"),
        ("email_materials", "parameters", {}, "email"),
        ("web_materials", "renderer_version", "unknown-renderer", "web"),
        ("web_materials", "email_binding", {"revision": 99, "digest": "0" * 64}, "web"),
        ("rubric_definitions", "content_digest", "0" * 64, "rubric"),
    ],
)
def test_corrupt_persisted_sources_cannot_pass_readiness(
    publication_env, table, field, value, reason
):
    e = publication_env
    ready(e)
    receipt = confirm(e)
    with e.database.engine.begin() as db:
        payload = json.loads(
            db.exec_driver_sql(f"SELECT payload FROM {table}").scalar_one()
        )
        payload[field] = value
        db.execute(
            text(f"UPDATE {table} SET revision=revision+1,payload=:p"),
            {"p": json.dumps(payload)},
        )
    report = e.readiness.evaluate(e.token, e.scenario, selected_group_ids=(e.group.id,))
    assert not report.technical_ready
    assert next(c for c in report.checks if c.check_id == reason).status == "BLOCKED"
    with pytest.raises(ApplicationError):
        e.publications.publish(
            e.token, e.scenario, confirmation_id=receipt.confirmation_id
        )
    assert count(e, "scenario_publications") == 0


def test_confirmation_requires_attestation_and_exact_group_snapshot(publication_env):
    e = publication_env
    report = ready(e)
    with pytest.raises(ApplicationError):
        e.readiness.confirm(
            e.token,
            e.scenario,
            review_fingerprint=report.review_fingerprint,
            selected_group_ids=(e.group.id,),
            acknowledged_warnings=report.acknowledgement_requirements,
            semantic_review=False,
        )
    other = e.groups.save_group(
        e.tokens["admin"], "Додаткова", instructors=(e.teacher_id,), learners=()
    )
    with pytest.raises(ApplicationError):
        e.readiness.confirm(
            e.token,
            e.scenario,
            review_fingerprint=report.review_fingerprint,
            selected_group_ids=(other.id,),
            acknowledged_warnings=report.acknowledgement_requirements,
            semantic_review=True,
        )
    assert count(e, "publication_reviews") == 0


def test_concurrent_grant_transition_and_forbidden_private_reads(publication_env):
    e = publication_env
    pub = publish(e)
    barrier = Barrier(2)

    def revoke(_):
        barrier.wait(timeout=5)
        try:
            e.publications.change_grant(
                e.token, pub.id, e.group.id, active=False, expected_revision=1
            )
            return "revoked"
        except ApplicationError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(revoke, range(2))) == ["conflict", "revoked"]
    assert [a.operation for a in e.publications.audit(e.token, pub.id)] == [
        "grant",
        "revoke",
    ]
    for token in (None, e.tokens["other"], e.tokens["learner"]):
        for operation in (
            lambda token=token: e.publications.history(token, e.scenario.id),
            lambda token=token: e.publications.audit(token, pub.id),
            lambda token=token: e.publications.grants(token, pub.id),
        ):
            with pytest.raises(ApplicationError):
                operation()
    with pytest.raises(ApplicationError):
        e.access.catalog(None)
    with pytest.raises(ApplicationError):
        e.access.catalog(e.token)


def test_publication_survives_database_and_service_restart(publication_env):
    from pathlib import Path

    from cyberforge.application.accounts import AccountService
    from cyberforge.application.scenarios import ScenarioService
    from cyberforge.persistence.database import Database

    e = publication_env
    pub = publish(e)
    database = Database(Path(e.database.engine.url.database))
    try:
        accounts = AccountService(database)
        token = accounts.login("teacher", e.password)
        integration = ScenarioIntegrationService(
            WebMaterialService(
                EmailMaterialService(ScenarioService(accounts), create_gateway())
            )
        )
        publications = ScenarioPublicationService(ScenarioReadinessService(integration))
        assert publications.history(token, e.scenario.id) == (pub,)
        learner = accounts.login("learner", e.password)
        assert PublicationAccessService(publications).resolve_internal(learner, pub.id)
    finally:
        database.close()
