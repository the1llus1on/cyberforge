"""F-01: draft provenance is independent of refinement and authorization."""

import json
import socket

import pytest

from cyberforge.agents import EmailScenarioAgent, WebScenarioAgent
from cyberforge.agents.contracts import WebInputV1
from cyberforge.agents.demo import (
    email_input,
    email_payload,
    scripted_gateway,
    web_payload,
)
from cyberforge.domain.scenarios import Difficulty
from cyberforge.llm.contracts import ErrorCategory


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("provenance regression attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def generate_email(source):
    payload = email_payload(source)
    payload["claimed_cues"] = [cue.value for cue in source.parameters.nist_cues]
    gateway, _ = scripted_gateway(payload)
    result = EmailScenarioAgent(gateway).run(source)
    assert result.status == "pending_review"
    return result.draft


def web_input(source, email):
    return WebInputV1(
        **source.model_dump(exclude={"previous"}), email=email, template="notice"
    )


def generate_web(source):
    gateway, _ = scripted_gateway(web_payload(source))
    result = WebScenarioAgent(gateway).run(source)
    assert result.status == "pending_review"
    return result.draft


@pytest.mark.parametrize("agent_kind", ["email", "web"])
@pytest.mark.parametrize(
    "changed", ["scenario_id", "scenario_version", "context", "parameters"]
)
def test_previous_from_other_source_with_same_resource_fails_before_llm(
    agent_kind, changed
):
    original = email_input()
    original_email = generate_email(original)
    original_web = generate_web(web_input(original, original_email))
    updates = {
        "scenario_id": 2,
        "scenario_version": 2,
        "context": original.context.model_copy(
            update={"premise": "Інша навчальна передумова"}
        ),
        "parameters": original.parameters.model_copy(
            update={"topic": "Інша навчальна тема"}
        ),
    }
    current = original.model_copy(update={changed: updates[changed]})
    assert current.context.internal_resource_id == original.context.internal_resource_id
    if agent_kind == "email":
        request = current.model_copy(update={"previous": original_email})
        agent_type = EmailScenarioAgent
    else:
        request = web_input(current, generate_email(current)).model_copy(
            update={"previous": original_web}
        )
        agent_type = WebScenarioAgent
    gateway, mock = scripted_gateway()
    result = agent_type(gateway).run(request)
    assert result.error == ErrorCategory.REQUEST
    assert result.generation_count == 0 and mock.calls == 0


@pytest.mark.parametrize("agent_kind", ["email", "web"])
@pytest.mark.parametrize(
    "refinement", [None, "Змініть формулювання.", "Уточніть навчальну мету в тексті."]
)
def test_same_source_regeneration_preserves_provenance_across_refinements(
    agent_kind, refinement
):
    source = email_input()
    email = generate_email(source)
    if agent_kind == "email":
        original_request, previous = source, email
        agent_type, payload = EmailScenarioAgent, email_payload
    else:
        original_request = web_input(source, email)
        previous = generate_web(original_request)
        agent_type, payload = WebScenarioAgent, web_payload
    request = original_request.model_copy(
        update={"previous": previous, "refinement": refinement}
    )
    before = previous.model_dump_json()
    gateway, mock = scripted_gateway(payload(request))
    result = agent_type(gateway).run(request)
    assert result.status == "pending_review" and mock.calls == 1
    assert result.draft.provenance == previous.provenance
    assert previous.model_dump_json() == before
    if refinement:
        assert agent_type.context_token(request) != previous.slots.context_token
    # Serialization must preserve local provenance and successful reuse.
    restored = agent_type.input_type.model_validate_json(request.model_dump_json())
    gateway, mock = scripted_gateway(payload(restored))
    assert agent_type(gateway).run(restored).status == "pending_review"
    assert mock.calls == 1


@pytest.mark.parametrize("changed", ["subject", "body_text", "background"])
def test_web_previous_bound_to_exact_associated_email(changed):
    source = email_input()
    old_email = generate_email(source)
    previous = generate_web(web_input(source, old_email))
    payload = email_payload(source)
    if changed == "background":
        payload["background"][0]["subject"] = "Змінене фонове повідомлення"
    else:
        payload["main"][changed] = "Змінений навчальний текст"
    gateway, _ = scripted_gateway(payload)
    new_email = EmailScenarioAgent(gateway).run(source).draft
    assert new_email.provenance == old_email.provenance
    request = web_input(source, new_email).model_copy(update={"previous": previous})
    gateway, mock = scripted_gateway()
    result = WebScenarioAgent(gateway).run(request)
    assert result.error == ErrorCategory.REQUEST and mock.calls == 0


@pytest.mark.parametrize("agent_kind", ["email", "web"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("topic", "Оновлена тема"),
        ("difficulty", Difficulty.ADVANCED),
        ("audience", "Оновлена синтетична аудиторія"),
        ("learning_objective", "Оновлена навчальна мета"),
        ("tactics", ("Синтетична терміновість",)),
        ("nist_cues", ()),
        ("generation_parameters", {"language": "en"}),
    ],
)
def test_changed_parameters_make_previous_stale(agent_kind, field, value):
    source = email_input()
    email = generate_email(source)
    previous = (
        email if agent_kind == "email" else generate_web(web_input(source, email))
    )
    changed = source.model_copy(
        update={"parameters": source.parameters.model_copy(update={field: value})}
    )
    agent_type = EmailScenarioAgent if agent_kind == "email" else WebScenarioAgent
    request = (
        changed
        if agent_kind == "email"
        else web_input(changed, generate_email(changed))
    )
    request = request.model_copy(update={"previous": previous})
    gateway, mock = scripted_gateway()
    assert agent_type(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


@pytest.mark.parametrize(
    "field", ["scenario_id", "scenario_version", "context", "parameters"]
)
def test_canonical_email_from_different_source_rejected_before_web_generation(field):
    source = email_input()
    email = generate_email(source)
    request = web_input(source, email)
    updates = {
        "scenario_id": 99,
        "scenario_version": 99,
        "context": source.context.model_copy(
            update={"organization": "Інша синтетична установа"}
        ),
        "parameters": source.parameters.model_copy(
            update={"topic": "Інший навчальний контекст"}
        ),
    }
    request = request.model_copy(update={field: updates[field]})
    gateway, mock = scripted_gateway()
    assert WebScenarioAgent(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


@pytest.mark.parametrize("agent_kind", ["email", "web"])
@pytest.mark.parametrize("legacy", ["slots", "envelope_without_provenance"])
def test_legacy_drafts_readable_but_cannot_regenerate_without_provenance(
    agent_kind, legacy
):
    source = email_input()
    email = generate_email(source)
    request = source if agent_kind == "email" else web_input(source, email)
    draft = email if agent_kind == "email" else generate_web(request)
    data = draft.model_dump(mode="json")
    del data["provenance"]
    legacy_draft = type(draft).model_validate_json(json.dumps(data))
    assert legacy_draft.provenance is None
    previous = draft.slots if legacy == "slots" else legacy_draft
    request = request.model_copy(update={"previous": previous})
    agent_type = EmailScenarioAgent if agent_kind == "email" else WebScenarioAgent
    gateway, mock = scripted_gateway()
    assert agent_type(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


@pytest.mark.parametrize("field", ["scenario_id", "scenario_version"])
def test_altering_email_envelope_identity_does_not_rebind_provenance(field):
    source = email_input()
    email = generate_email(source)
    changed = source.model_copy(update={field: 2})
    relabeled = email.model_copy(update={field: 2})
    request = web_input(source, email).model_copy(update={field: 2, "email": relabeled})
    gateway, mock = scripted_gateway()
    assert WebScenarioAgent(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0
    gateway, mock = scripted_gateway()
    assert (
        EmailScenarioAgent(gateway)
        .run(changed.model_copy(update={"previous": relabeled}))
        .error
        == ErrorCategory.REQUEST
    )
    assert mock.calls == 0


@pytest.mark.parametrize("agent_kind", ["email", "web"])
def test_changed_language_is_stale_but_not_refinement(agent_kind):
    source = email_input()
    email = generate_email(source)
    if agent_kind == "email":
        request, previous, agent_type = source, email, EmailScenarioAgent
    else:
        request = web_input(source, email)
        previous, agent_type = generate_web(request), WebScenarioAgent
    request = request.model_copy(update={"language": "en", "previous": previous})
    gateway, mock = scripted_gateway()
    assert agent_type(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


def test_web_template_is_part_of_stable_provenance():
    source = email_input()
    request = web_input(source, generate_email(source))
    previous = generate_web(request)
    request = request.model_copy(update={"template": "portal", "previous": previous})
    gateway, mock = scripted_gateway()
    assert WebScenarioAgent(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


def test_legacy_email_cannot_seed_web_generation():
    source = email_input()
    email = generate_email(source)
    request = web_input(source, email).model_copy(
        update={"email": email.model_copy(update={"provenance": None})}
    )
    gateway, mock = scripted_gateway()
    assert WebScenarioAgent(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


@pytest.mark.parametrize("field", ["scenario_id", "scenario_version"])
def test_unknown_identity_cannot_be_reused(field):
    source = email_input().model_copy(update={field: None})
    previous = generate_email(source)
    gateway, mock = scripted_gateway()
    assert (
        EmailScenarioAgent(gateway)
        .run(source.model_copy(update={"previous": previous}))
        .error
        == ErrorCategory.REQUEST
    )
    assert mock.calls == 0


def test_relabeling_previous_web_template_does_not_bypass_linkage():
    source = email_input()
    request = web_input(source, generate_email(source))
    previous = generate_web(request)
    previous = previous.model_copy(
        update={"slots": previous.slots.model_copy(update={"template": "portal"})}
    )
    request = request.model_copy(update={"previous": previous})
    gateway, mock = scripted_gateway()
    assert WebScenarioAgent(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


@pytest.mark.parametrize("field", ["scenario_id", "scenario_version"])
def test_web_rejects_missing_expected_identity_before_generation(field):
    source = email_input()
    request = web_input(source, generate_email(source)).model_copy(update={field: None})
    gateway, mock = scripted_gateway()
    assert WebScenarioAgent(gateway).run(request).error == ErrorCategory.REQUEST
    assert mock.calls == 0


def test_web_regeneration_survives_email_refinement_without_content_change():
    source = email_input()
    email = generate_email(source)
    previous = generate_web(web_input(source, email))
    refined = source.model_copy(update={"refinement": "Збережіть навчальний зміст."})
    refined_email = generate_email(refined)
    assert refined_email.provenance == email.provenance
    assert refined_email.slots.context_token != email.slots.context_token
    before = email.slots.model_dump(mode="json", exclude={"context_token"})
    after = refined_email.slots.model_dump(mode="json", exclude={"context_token"})
    assert before == after
    request = web_input(source, refined_email).model_copy(
        update={"previous": previous, "refinement": "Уточніть заголовок сторінки."}
    )
    gateway, mock = scripted_gateway(web_payload(request))
    result = WebScenarioAgent(gateway).run(request)
    assert result.status == "pending_review" and mock.calls == 1
    assert result.draft.provenance == previous.provenance
