"""Manual working drafts, authorized context rebinding and protected refinement."""

import json
import socket

import pytest

from cyberforge.agents.contracts import EmailDraftV2, MessageV1
from cyberforge.application.email_materials import EmailMaterialService, email_source
from cyberforge.domain.accounts import ApplicationError
from cyberforge.llm.factory import create_gateway


@pytest.fixture
def editing(scenario_env, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *a: pytest.fail("Network"))
    env = scenario_env
    env.token = env.tokens["teacher"]
    env.emails = EmailMaterialService(env.service, create_gateway(), demo=True)
    env.scenario = env.service.create(
        env.token, dict(topic="Навчальна перевірка", difficulty="beginner")
    )
    env.workspace = env.emails.load(env.token, env.scenario)
    env.draft = env.emails.generate(env.token, env.workspace)
    return env


def revised(message, **values):
    return MessageV1.model_validate_json(
        json.dumps(message.model_dump(mode="json") | values)
    )


def test_manual_main_background_save_reopen_and_refine(editing):
    e = editing
    saved = e.emails.save(e.token, e.workspace, e.draft)
    entry = revised(
        e.draft.slots.main,
        sender_name="Синтетична редакція",
        sender_address="editor@school.invalid",
        subject="Ручна тема",
        body_text="Ручний текст.",
    )
    manual = e.emails.edit(e.token, saved, saved.draft, index=0, message=entry)
    manual = e.emails.edit(
        e.token,
        saved,
        manual,
        index=1,
        message=revised(manual.slots.background[0], subject="Ручна фонова тема"),
    )
    assert manual.artifact.subject == manual.slots.main.subject == entry.subject
    assert manual.artifact.body_text == entry.body_text
    assert (
        manual.artifact.context.sender_name
        == manual.instructor_sender_name
        == entry.sender_name
    )
    assert manual.scenario_id == e.draft.scenario_id
    assert manual.slots.internal_resource_id == e.draft.slots.internal_resource_id
    assert manual.verified_cues == () and manual.selected_cues == e.draft.selected_cues
    assert e.emails.load(e.token, e.scenario).draft == e.draft
    source = email_source(e.scenario, previous=manual)
    assert source.previous == manual and source.context == manual.artifact.context
    refined = e.emails.generate(
        e.token,
        saved,
        previous=manual,
        refinement="Скороти лише текст основного листа",
        refinement_scope="main_body",
    )
    assert refined.slots.main.subject == manual.slots.main.subject
    assert refined.slots.main.sender_address == manual.slots.main.sender_address
    assert refined.slots.background == manual.slots.background
    assert refined.slots.main.body_text != manual.slots.main.body_text
    assert refined.provenance == manual.provenance
    assert e.emails.load(e.token, e.scenario).draft == e.draft
    final = e.emails.save(e.token, saved, refined)
    assert e.emails.load(e.token, e.scenario) == final
    again = e.emails.edit(e.token, final, final.draft, index=0, message=entry)
    assert again.artifact.context == manual.artifact.context


@pytest.mark.parametrize(
    "field,value",
    [
        ("sender_address", "teacher@example.com"),
        ("body_text", "<script>alert(1)</script>"),
        ("body_text", "https://example.com"),
        ("body_text", "password=private-secret"),
        ("body_text", "x" * 4001),
        ("sender_name", "x" * 201),
        ("subject", ""),
    ],
)
def test_invalid_edits_fail_without_mutation(editing, field, value):
    e = editing
    payload = e.draft.slots.main.model_dump() | {field: value}
    untrusted = MessageV1.model_construct(**payload)
    with pytest.raises(ApplicationError):
        e.emails.edit(e.token, e.workspace, e.draft, index=0, message=untrusted)
    assert e.emails.load(e.token, e.scenario).draft is None


def test_background_bounds_and_unrelated_message_preservation(editing):
    e = editing
    draft = e.draft
    for _ in range(6):
        draft = e.emails.edit(
            e.token,
            e.workspace,
            draft,
            index=1,
            action="add",
            message=draft.slots.background[0],
        )
    assert len(draft.slots.background) == 8 and draft.slots.main == e.draft.slots.main
    with pytest.raises(ApplicationError):
        e.emails.edit(
            e.token, e.workspace, draft, index=1, action="add", message=draft.slots.main
        )
    for _ in range(7):
        draft = e.emails.edit(e.token, e.workspace, draft, index=1, action="remove")
    with pytest.raises(ApplicationError):
        e.emails.edit(e.token, e.workspace, draft, index=1, action="remove")
    with pytest.raises(ApplicationError):
        e.emails.edit(e.token, e.workspace, draft, index=0, action="remove")


@pytest.mark.parametrize("actor", ["learner", "other"])
def test_manual_service_rejects_unauthorized_actor(editing, actor):
    e = editing
    with pytest.raises(ApplicationError):
        e.emails.edit(
            e.tokens[actor], e.workspace, e.draft, index=0, message=e.draft.slots.main
        )


def test_previous_validation_and_failed_refinement_keep_manual(editing, monkeypatch):
    e = editing
    manual = e.emails.edit(
        e.token,
        e.workspace,
        e.draft,
        index=0,
        message=revised(e.draft.slots.main, subject="Ручна тема"),
    )
    before = manual.model_dump_json()
    from cyberforge.agents.specialized import EmailScenarioAgent

    monkeypatch.setattr(
        EmailScenarioAgent, "run", lambda *a: (_ for _ in ()).throw(ValueError())
    )
    with pytest.raises(ApplicationError):
        e.emails.generate(e.token, e.workspace, previous=manual)
    assert manual.model_dump_json() == before
    changed = e.service.update(
        e.token,
        e.scenario.id,
        e.scenario.parameters.model_dump() | {"topic": "Нова тема"},
        expected_version=1,
        expected_revision=1,
    )
    with pytest.raises(ApplicationError):
        e.emails.edit(e.token, e.workspace, manual, index=0, message=manual.slots.main)
    assert changed.revision == 2


def test_old_payload_without_override_still_valid(editing):
    e = editing
    payload = e.draft.model_dump(mode="json")
    payload.pop("instructor_sender_name")
    old = EmailDraftV2.model_validate_json(json.dumps(payload))
    assert old == e.draft
    e.emails.save(e.token, e.workspace, old)
    assert e.emails.load(e.token, e.scenario).draft == old


@pytest.mark.parametrize("restriction", ["archive", "published", "foreign_version"])
def test_manual_edit_preserves_version_restrictions(editing, restriction):
    from sqlalchemy import text

    e = editing
    if restriction == "archive":
        e.service.archive(
            e.token,
            e.scenario.id,
            expected_version=1,
            expected_revision=1,
            expected_archive_revision=0,
        )
    elif restriction == "published":
        with e.database.engine.begin() as db:
            db.execute(text("UPDATE scenario_versions SET status='published'"))
    else:
        e.draft = e.draft.model_copy(update={"scenario_version": 99})
    with pytest.raises(ApplicationError):
        e.emails.edit(
            e.token, e.workspace, e.draft, index=0, message=e.draft.slots.main
        )
