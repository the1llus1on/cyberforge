"""Versioned component contracts, provider projection and deterministic scopes."""

import json

import pytest
from pydantic import ValidationError

from cyberforge.agents.demo import email_input, email_payload, scripted_gateway
from cyberforge.agents.specialized import EmailScenarioAgent
from cyberforge.agents.web import WebScenarioAgentV2
from cyberforge.application.web_demo import demo_gateway
from cyberforge.llm.schemas import groq_strict_schema
from cyberforge.web.contracts import (
    COMPONENTS,
    PRESETS,
    THEMES,
    EmailBindingV2,
    WebDraftV3,
    WebInputV2,
    WebPageV2,
    WebSlotsV2,
    email_digest,
)
from cyberforge.web.presets import default_component, preset_components, wire_component


@pytest.fixture
def web_source():
    source = email_input()
    gateway, _ = scripted_gateway(email_payload(source))
    email = EmailScenarioAgent(gateway).run(source).draft
    return WebInputV2(
        synthetic=True,
        scenario_id=1,
        scenario_version=1,
        parameters=source.parameters,
        context=source.context,
        email=email,
        email_binding=EmailBindingV2(revision=1, digest=email_digest(email)),
    )


def generated(source):
    result = WebScenarioAgentV2(demo_gateway(source)).run(source)
    assert result.status == "pending_review", result.error
    return result.draft


def page_data():
    return dict(
        tab_title="Навчальний сайт",
        display_url="https://portal.example/course?q=1#intro",
        internal_resource_id="training_notice",
        theme="academic",
        components=preset_components("auto"),
    )


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("theme", THEMES)
def test_presets_themes_and_automatic(web_source, preset, theme):
    source = WebInputV2.model_validate_json(
        json.dumps(
            web_source.model_dump(mode="json") | {"preset": preset, "theme": theme}
        )
    )
    draft = generated(source)
    assert draft.preset == preset and draft.page.theme == theme
    assert WebDraftV3.model_validate_json(draft.model_dump_json()) == draft


@pytest.mark.parametrize("kind", COMPONENTS)
def test_all_component_types(kind):
    data = page_data()
    data["components"] = [
        default_component("header", "first"),
        default_component(kind, "current"),
        default_component("footer", "last"),
    ]
    if kind == "header":
        data["components"][0] = default_component("text", "first")
        data["components"][0], data["components"][1] = (
            data["components"][1],
            data["components"][0],
        )
    if kind == "footer":
        data["components"][-1] = default_component("text", "last")
        data["components"][-1], data["components"][1] = (
            data["components"][1],
            data["components"][-1],
        )
    assert WebPageV2.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "url",
    [
        "https://www.googIe.com",
        "https://portal.osvita.example/a",
        "https://alpha.invalid/",
    ],
)
def test_realistic_addresses_are_inert_data(url):
    assert (
        WebPageV2.model_validate_json(
            json.dumps(page_data() | {"display_url": url})
        ).display_url
        == url
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://site.example",
        "file:///etc/passwd",
        "https://user:pass@site.example",
        "https://site.example/\n",
        "https://site.example/%0d%0aHeader",
        "https://site.example\\@evil.example",
        "https://site.example/%5c",
        "https://site.example:70000",
        "https:///missing",
        "https://a..example",
    ],
)
def test_invalid_addresses(url):
    with pytest.raises(ValueError):
        WebPageV2.model_validate_json(json.dumps(page_data() | {"display_url": url}))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["components"][1].update(id=d["components"][0]["id"]),
        lambda d: d["components"][1].update(id="bad/id"),
        lambda d: d["components"][1].update(type="script"),
        lambda d: d["components"][1].update(html="code"),
        lambda d: d["components"][1].update(text="<script>alert(1)</script>"),
        lambda d: d.update(theme="external"),
        lambda d: d.update(components=d["components"][:2]),
        lambda d: d["components"].reverse(),
        lambda d: d["components"][1]["actions"][0].update(id="download"),
    ],
)
def test_malformed_compositions(mutation):
    data = page_data()
    mutation(data)
    with pytest.raises(ValueError):
        WebPageV2.model_validate_json(json.dumps(data))


def test_strict_wire_schema_stays_simple(web_source):
    schema = groq_strict_schema(WebSlotsV2.model_json_schema())
    assert "anyOf" not in json.dumps(schema)
    draft = generated(web_source)
    data = draft.page.model_dump(mode="json", exclude={"schema_version"}) | dict(
        schema_version="web-slots-v2",
        context_token="token",
        components=[
            wire_component(c) for c in draft.page.model_dump(mode="json")["components"]
        ],
    )
    assert WebSlotsV2.model_validate_json(json.dumps(data))
    data["components"][0]["actions"] = [{"id": "confirm", "label": "No"}]
    with pytest.raises(ValidationError):
        WebSlotsV2.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("scope", ["text", "component"])
def test_protected_refinement(web_source, scope):
    old = generated(web_source)
    source = WebInputV2.model_validate_json(
        json.dumps(
            web_source.model_dump(mode="json")
            | dict(
                previous=old.model_dump(mode="json"),
                refinement="Скороти текст",
                refinement_scope=scope,
                selected_component=old.page.components[1].id,
            )
        )
    )
    candidate = old.page.model_dump(mode="json", exclude={"schema_version"}) | dict(
        schema_version="web-slots-v2",
        context_token=WebScenarioAgentV2.context_token(source),
        theme="service",
        tab_title="Небажана зміна",
        display_url="https://different.example/",
        components=[
            wire_component(c) for c in old.page.model_dump(mode="json")["components"]
        ],
    )
    candidate["components"][1]["text"] = "Новий текст"
    candidate["components"][0]["title"] = "Інший заголовок"
    result = WebScenarioAgentV2(demo_gateway(source)).validate_output(
        source, WebSlotsV2.model_validate_json(json.dumps(candidate))
    )
    assert result.page.tab_title == old.page.tab_title
    assert result.page.display_url == old.page.display_url
    assert result.page.theme == old.page.theme
    assert result.source_digest == old.source_digest
    assert result.page.components[1].text == "Новий текст"
    if scope == "component":
        assert result.page.components[0] == old.page.components[0]
    else:
        assert result.page.components[0].title == "Інший заголовок"


def test_identity_and_stale_provenance_rejected(web_source):
    draft = generated(web_source)
    for update in (
        {"scenario_id": 2},
        {"source_digest": "0" * 64},
        {"email_binding": {"revision": 2, "digest": "0" * 64}},
    ):
        with pytest.raises(ValueError):
            WebDraftV3.model_validate_json(
                json.dumps(draft.model_dump(mode="json") | update)
            )
    with pytest.raises(ValueError):
        WebInputV2.model_validate_json(
            json.dumps(web_source.model_dump(mode="json") | {"scenario_version": 2})
        )


def test_v2_refinement_accepts_realistic_display_address_without_changing_legacy(
    web_source,
):
    source = WebInputV2.model_validate_json(
        json.dumps(
            web_source.model_dump(mode="json")
            | {"refinement": "Покажи навчальну адресу https://portal.example/course"}
        )
    )
    assert source.refinement.endswith("/course")
    for address in (
        "https://portal.example:8443/course",
        "https://освіта.example/курс",
    ):
        assert WebPageV2.model_validate_json(
            json.dumps(page_data() | {"display_url": address})
        )
    for address in (
        "https://portal.example/\u202eexe",
        "https://portal.example/%E2%80%AEexe",
    ):
        with pytest.raises(ValueError):
            WebPageV2.model_validate_json(
                json.dumps(page_data() | {"display_url": address})
            )
