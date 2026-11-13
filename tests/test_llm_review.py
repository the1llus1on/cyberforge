"""Independent review regressions: fallback settings and artifact schemas."""

import json
from copy import deepcopy

import httpx
import pytest
from groq import Groq
from pydantic import SecretStr

from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import (
    EmailArtifactV1,
    ErrorCategory,
    GenerationError,
    GenerationParameters,
    GenerationRequest,
    Provider,
    ProviderResponse,
    WebArtifactV1,
)
from cyberforge.llm.gateway import GenerationFailure, LLMGateway
from cyberforge.llm.groq_provider import GroqProvider
from cyberforge.llm.schemas import groq_output_schema, groq_strict_schema


class RecordingProvider:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.schemas = []

    def generate(self, request, schema):
        self.requests.append(request)
        self.schemas.append(schema)
        if isinstance(self.response, GenerationError):
            raise self.response
        return ProviderResponse(text=self.response, actual_model=request.model)


def artifact_payload(output_type, resource_id="review_resource-1"):
    context = {
        "schema_version": "scenario-context-v1",
        "organization": "Synthetic organization",
        "sender_name": "Synthetic sender",
        "premise": "Synthetic training fixture",
        "internal_resource_id": resource_id,
    }
    if output_type is EmailArtifactV1:
        return {
            "schema_version": "email-artifact-v1",
            "context": context,
            "subject": "Synthetic subject",
            "body_text": "Synthetic body",
        }
    return {
        "schema_version": "web-artifact-v1",
        "context": context,
        "heading": "Synthetic heading",
        "body_text": "Synthetic body",
        "action_label": "Continue",
    }


def request(**updates):
    return GenerationRequest(
        prompt="Synthetic review fixture", synthetic=True, **updates
    )


def test_minimal_fallback_preserves_request_and_uses_explicit_low():
    primary = RecordingProvider(GenerationError(ErrorCategory.UNAVAILABLE))
    backup = RecordingProvider("Synthetic result")
    gateway = LLMGateway(
        GatewayConfig(max_retries=0, fallback_to_groq=True),
        {Provider.GEMINI: primary, Provider.GROQ: backup},
    )
    original = request(
        provider=Provider.GEMINI,
        model="gemini-3.5-flash-lite",
        parameters=GenerationParameters(thinking="minimal"),
    )
    result = gateway.generate(original)
    assert backup.requests[0].parameters.thinking == "low"
    assert original.parameters.thinking == "minimal"
    assert result.telemetry.fallback


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
def test_canonical_artifact_is_usable_through_groq(output_type):
    provider = RecordingProvider(json.dumps(artifact_payload(output_type)))
    gateway = LLMGateway(GatewayConfig(), {Provider.GROQ: provider})
    result = gateway.generate(
        request(
            provider=Provider.GROQ,
            model="openai/gpt-oss-120b",
            operation="structured",
            schema_version="artifact-v1",
        ),
        output_type,
    )
    assert isinstance(result.structured, output_type)
    assert result.telemetry.local_validation == "passed"


THINKING_CASES = [
    ("gemini-3.8-flash", level) for level in (None, "low", "medium", "high")
] + [
    ("gemini-3.5-flash-lite", level)
    for level in (None, "minimal", "low", "medium", "high")
]


@pytest.mark.parametrize("model,thinking", THINKING_CASES)
@pytest.mark.parametrize("category", [ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE])
def test_fallback_parameter_policy_and_telemetry(model, thinking, category):
    primary = RecordingProvider(GenerationError(category))
    backup = RecordingProvider("Synthetic result")
    gateway = LLMGateway(
        GatewayConfig(max_retries=0, fallback_to_groq=True),
        {Provider.GEMINI: primary, Provider.GROQ: backup},
    )
    original = request(
        provider=Provider.GEMINI,
        model=model,
        parameters=GenerationParameters(
            thinking=thinking,
            temperature=0.65,
            max_output_tokens=321,
            timeout_seconds=17,
        ),
    )
    before = original.parameters.model_dump()
    result = gateway.generate(original)
    effective = backup.requests[0]
    assert effective.provider == Provider.GROQ
    assert effective.model == "openai/gpt-oss-120b"
    assert effective.parameters.model_dump() == {
        **before,
        "thinking": "low" if thinking == "minimal" else thinking,
    }
    assert primary.requests[0] is original
    assert original.parameters.model_dump() == before
    assert result.telemetry.requested_parameters == original.parameters
    assert result.telemetry.effective_parameters == effective.parameters
    assert result.telemetry.requested_model == model
    assert result.telemetry.actual_model == effective.model
    assert result.telemetry.schema_projection is None
    assert original.prompt not in result.model_dump_json()
    assert len(primary.requests) == len(backup.requests) == 1


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
@pytest.mark.parametrize(
    "category",
    [
        category
        for category in ErrorCategory
        if category not in {ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE}
    ],
)
def test_artifact_minimal_does_not_bypass_fallback_denylist(output_type, category):
    primary = RecordingProvider(GenerationError(category))
    backup = RecordingProvider(json.dumps(artifact_payload(output_type)))
    gateway = LLMGateway(
        GatewayConfig(max_retries=0, fallback_to_groq=True),
        {Provider.GEMINI: primary, Provider.GROQ: backup},
    )
    original = request(
        provider=Provider.GEMINI,
        model="gemini-3.5-flash-lite",
        parameters=GenerationParameters(thinking="minimal"),
        operation="structured",
        schema_version="artifact-v1",
    )
    with pytest.raises(GenerationFailure) as caught:
        gateway.generate(original, output_type)
    assert caught.value.category == category
    assert caught.value.telemetry.fallback is False
    assert caught.value.telemetry.requested_parameters == original.parameters
    assert caught.value.telemetry.effective_parameters == original.parameters
    assert backup.requests == []


def test_disabled_fallback_does_not_map_minimal():
    primary = RecordingProvider(GenerationError(ErrorCategory.UNAVAILABLE))
    backup = RecordingProvider("Synthetic")
    gateway = LLMGateway(
        GatewayConfig(max_retries=0),
        {Provider.GEMINI: primary, Provider.GROQ: backup},
    )
    with pytest.raises(GenerationFailure, match="unavailable") as caught:
        gateway.generate(
            request(
                provider=Provider.GEMINI,
                model="gemini-3.5-flash-lite",
                parameters=GenerationParameters(thinking="minimal"),
            )
        )
    assert caught.value.telemetry.effective_parameters.thinking == "minimal"
    assert backup.requests == []


@pytest.mark.parametrize(
    "provider,model",
    [
        (Provider.GEMINI, "gemini-3.8-flash"),
        (Provider.GROQ, "openai/gpt-oss-120b"),
    ],
)
def test_invalid_original_thinking_is_not_repaired(provider, model):
    transport = RecordingProvider("Synthetic")
    gateway = LLMGateway(
        GatewayConfig(fallback_to_groq=True),
        {Provider.GEMINI: transport, Provider.GROQ: transport},
    )
    with pytest.raises(GenerationFailure, match="configuration"):
        gateway.generate(
            request(
                provider=provider,
                model=model,
                parameters=GenerationParameters(thinking="minimal"),
            )
        )
    assert transport.requests == []


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
def test_projection_is_exact_non_mutating_and_preserves_canonical_regex(output_type):
    original = output_type.model_json_schema()
    before = deepcopy(original)
    field = original["$defs"]["ScenarioContextV1"]["properties"]["internal_resource_id"]
    assert field["pattern"] == r"^[a-zA-Z0-9_-]{1,64}$"
    # Exact baseline incompatibility remains explicit for the raw strict checker.
    with pytest.raises(GenerationError, match="unsupported_schema"):
        groq_strict_schema(original)
    projected, marker = groq_output_schema(output_type, original)
    assert marker == "groq-artifact-v1-local-resource-id"
    assert projected["properties"]["context"]["properties"]["internal_resource_id"] == {
        "type": "string"
    }
    assert projected["additionalProperties"] is False
    assert projected["properties"]["context"]["additionalProperties"] is False
    assert set(projected["required"]) == set(projected["properties"])
    assert projected["properties"]["schema_version"]["enum"] == [
        "email-artifact-v1" if output_type is EmailArtifactV1 else "web-artifact-v1"
    ]
    assert original == before
    assert output_type.model_json_schema() == before


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
def test_projection_fails_closed_on_changed_constraints(output_type):
    schema = output_type.model_json_schema()
    schema["$defs"]["ScenarioContextV1"]["properties"]["internal_resource_id"][
        "pattern"
    ] = "^different$"
    with pytest.raises(GenerationError, match="unsupported_schema"):
        groq_output_schema(output_type, schema)
    schema = output_type.model_json_schema()
    schema["properties"]["body_text"]["pattern"] = "^unapproved$"
    with pytest.raises(GenerationError, match="unsupported_schema"):
        groq_output_schema(output_type, schema)


def groq_sdk_provider(payload, calls):
    def handler(req):
        calls.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "created": 0,
                "object": "chat.completion",
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(payload),
                        },
                    }
                ],
            },
        )

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return Groq(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler))
        )

    return GroqProvider(SecretStr("synthetic-test-key"), client_factory=factory)


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("resource_id", ["a", "a" * 64, "review_resource-1"])
def test_artifact_real_groq_sdk_wire_schema_and_structured_fallback(
    output_type, fallback, resource_id
):
    calls = []
    payload = artifact_payload(output_type, resource_id)
    primary = RecordingProvider(GenerationError(ErrorCategory.UNAVAILABLE))
    gateway = LLMGateway(
        GatewayConfig(max_retries=0, fallback_to_groq=fallback),
        {Provider.GROQ: groq_sdk_provider(payload, calls), Provider.GEMINI: primary},
    )
    original = request(
        provider=Provider.GEMINI if fallback else Provider.GROQ,
        model="gemini-3.5-flash-lite" if fallback else "openai/gpt-oss-120b",
        operation="structured",
        schema_version="artifact-v1",
        parameters=GenerationParameters(thinking="minimal" if fallback else "low"),
    )
    result = gateway.generate(original, output_type)
    assert len(calls) == 1
    response_format = calls[0]["response_format"]["json_schema"]
    assert response_format["strict"] is True
    assert "pattern" not in json.dumps(response_format["schema"])
    assert calls[0]["reasoning_effort"] == "low"
    assert result.structured == output_type.model_validate(payload, strict=True)
    assert result.telemetry.local_validation == "passed"
    assert result.telemetry.schema_projection == "groq-artifact-v1-local-resource-id"
    assert result.telemetry.fallback == fallback
    assert result.telemetry.requested_parameters == original.parameters
    assert result.telemetry.effective_parameters.thinking == "low"
    if fallback:
        assert primary.schemas[0] == output_type.model_json_schema()
        assert original.parameters.thinking == "minimal"


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize(
    "resource_id",
    [
        "",
        "a" * 65,
        "../path",
        "https://example.invalid",
        "space id",
        "кирилиця",
        "resource\n",
        42,
    ],
)
def test_artifact_invalid_ids_fail_local_validation_after_groq(
    output_type, fallback, resource_id
):
    calls = []
    payload = artifact_payload(output_type, resource_id)
    gateway = LLMGateway(
        GatewayConfig(max_retries=0, fallback_to_groq=fallback),
        {
            Provider.GROQ: groq_sdk_provider(payload, calls),
            Provider.GEMINI: RecordingProvider(GenerationError(ErrorCategory.TIMEOUT)),
        },
    )
    with pytest.raises(GenerationFailure, match="validation") as caught:
        gateway.generate(
            request(
                provider=Provider.GEMINI if fallback else Provider.GROQ,
                model="gemini-3.5-flash-lite" if fallback else "openai/gpt-oss-120b",
                parameters=GenerationParameters(
                    thinking="minimal" if fallback else "low"
                ),
                operation="structured",
                schema_version="artifact-v1",
            ),
            output_type,
        )
    assert len(calls) == 1
    assert caught.value.telemetry.local_validation == "failed"
    assert (
        caught.value.telemetry.schema_projection == "groq-artifact-v1-local-resource-id"
    )
    assert caught.value.telemetry.fallback == fallback
