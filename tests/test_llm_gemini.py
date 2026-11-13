"""Real Google SDK serialization/parsing over deterministic HTTP transports."""

import json

import httpx
import pytest
from google import genai
from pydantic import SecretStr

from cyberforge.llm.contracts import (
    Contract,
    ErrorCategory,
    GenerationError,
    GenerationParameters,
    GenerationRequest,
    Provider,
)
from cyberforge.llm.gemini_provider import GeminiProvider


class Message(Contract):
    message: str


def request(model="gemini-3.8-flash", thinking="low"):
    return GenerationRequest(
        prompt="Synthetic input",
        synthetic=True,
        provider=Provider.GEMINI,
        model=model,
        parameters=GenerationParameters(thinking=thinking),
    )


def adapter(handler):
    def factory(**kwargs):
        options = kwargs["http_options"]
        assert options.retry_options.attempts == 1
        assert options.timeout == 30000
        assert options.api_version == "v1"
        assert kwargs["vertexai"] is False
        kwargs["http_options"] = options.model_copy(
            update={
                "httpx_client": httpx.Client(transport=httpx.MockTransport(handler)),
            }
        )
        return genai.Client(**kwargs)

    return GeminiProvider(SecretStr("synthetic-test-key"), client_factory=factory)


def payload(**updates):
    return {
        "id": "fixture",
        "status": "completed",
        "model": "gemini-3.8-flash",
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {"type": "text", "text": '{"message":"fixture"}'},
                ],
            }
        ],
        "usage": {
            "total_input_tokens": 10,
            "total_output_tokens": 12,
            "total_thought_tokens": 5,
            "total_tokens": 22,
        },
        **updates,
    }


@pytest.mark.parametrize("schema", [None, Message.model_json_schema()])
def test_stateless_single_request_schema_usage_and_timeout(schema, caplog, monkeypatch):
    caplog.set_level("DEBUG")
    monkeypatch.setenv("GOOGLE_GENAI_DEBUG", "1")
    captured = []

    def handler(req):
        captured.append(req)
        return httpx.Response(200, json=payload())

    response = adapter(handler).generate(request(), schema)
    assert len(captured) == 1
    req = captured[0]
    body = json.loads(req.content)
    assert req.url.host == "generativelanguage.googleapis.com"
    assert req.url.path == "/v1/interactions"
    assert body["store"] is False
    assert body["background"] is False
    assert "previous_interaction_id" not in body
    assert "tools" not in body
    assert "automatic_continuation" not in body
    assert body["generation_config"]["thinking_level"] == "low"
    assert body["generation_config"]["thinking_summaries"] == "none"
    if schema:
        assert body["response_format"] == {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        }
    else:
        assert "response_format" not in body
    assert response.text == '{"message":"fixture"}'
    assert response.actual_model == "gemini-3.8-flash"
    assert response.usage.input_tokens == 10
    assert response.usage.reasoning_tokens == 5
    assert "synthetic-test-key" not in caplog.text
    assert "Synthetic input" not in caplog.text


@pytest.mark.parametrize(
    "status,category",
    [
        (400, ErrorCategory.REQUEST),
        (401, ErrorCategory.AUTHORIZATION),
        (403, ErrorCategory.AUTHORIZATION),
        (404, ErrorCategory.REQUEST),
        (429, ErrorCategory.RATE_LIMIT),
        (500, ErrorCategory.UNAVAILABLE),
        (503, ErrorCategory.UNAVAILABLE),
    ],
)
def test_sdk_retries_disabled_and_errors_sanitized(status, category, caplog):
    caplog.set_level("DEBUG")
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            status,
            json={"error": {"code": status, "message": "private-secret"}},
            headers={"Retry-After": "7"},
        )

    with pytest.raises(GenerationError) as caught:
        adapter(handler).generate(request(), None)
    assert len(calls) == 1
    assert caught.value.category == category
    assert caught.value.retry_after == 7
    assert caught.value.__context__ is None
    assert "private-secret" not in str(caught.value)
    assert "synthetic-test-key" not in caplog.text
    assert "private-secret" not in caplog.text


def test_transport_timeout():
    def handler(req):
        raise httpx.ReadTimeout("private-secret", request=req)

    with pytest.raises(GenerationError, match="timeout"):
        adapter(handler).generate(request(), None)


@pytest.mark.parametrize(
    "status", ["incomplete", "requires_action", "requires_continuation"]
)
def test_no_automatic_continuation_or_partial_success(status):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            200, json=payload(status=status, continuation_token="private-token")
        )

    with pytest.raises(GenerationError, match="validation"):
        adapter(handler).generate(request(), None)
    assert len(calls) == 1


def test_safety_refusal_is_normalized():
    provider = adapter(
        lambda req: httpx.Response(
            200,
            json=payload(
                status="failed",
                errors=[
                    {"code": "https://example.invalid/safety", "message": "private"}
                ],
            ),
        )
    )
    with pytest.raises(GenerationError, match="safety_refusal"):
        provider.generate(request(), None)


def test_model_output_safety_details_and_unknown_fault_are_safe():
    for reason, category in [
        ("SAFETY", "safety_refusal"),
        ("UNKNOWN", "invalid_request"),
    ]:
        result = payload(
            steps=[
                {
                    "type": "model_output",
                    "error": {
                        "code": 3,
                        "message": "private-message",
                        "details": [{"reason": reason}],
                    },
                }
            ]
        )
        provider = adapter(lambda req, result=result: httpx.Response(200, json=result))
        with pytest.raises(GenerationError, match=category):
            provider.generate(request(), None)


def test_unsupported_sdk_retry_configuration_fails_before_request():
    from types import SimpleNamespace

    class UnsupportedClient:
        interactions = SimpleNamespace()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    provider = GeminiProvider(
        SecretStr("synthetic-test-key"),
        client_factory=lambda **kwargs: UnsupportedClient(),
    )
    with pytest.raises(GenerationError, match="configuration"):
        provider.generate(request(), None)


def test_absent_metadata_is_not_invented():
    response = adapter(
        lambda req: httpx.Response(200, json=payload(usage=None, model=None))
    ).generate(request(), None)
    assert response.actual_model is None
    assert response.usage.input_tokens is None


@pytest.mark.parametrize(
    "model,thinking",
    [
        ("gemini-3.8-flash", "low"),
        ("gemini-3.8-flash", "medium"),
        ("gemini-3.8-flash", "high"),
        ("gemini-3.5-flash-lite", "minimal"),
        ("gemini-3.5-flash-lite", "low"),
        ("gemini-3.5-flash-lite", "medium"),
        ("gemini-3.5-flash-lite", "high"),
    ],
)
def test_supported_thinking_levels(model, thinking):
    def handler(req):
        assert (
            json.loads(req.content)["generation_config"]["thinking_level"] == thinking
        )
        return httpx.Response(200, json=payload(model=model))

    adapter(handler).generate(request(model, thinking), None)


def test_missing_credentials_no_client():
    def forbidden(**kwargs):
        pytest.fail("client initialized without key")

    with pytest.raises(GenerationError, match="missing_credentials"):
        GeminiProvider(None, client_factory=forbidden).generate(request(), None)
