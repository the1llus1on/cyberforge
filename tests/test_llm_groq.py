"""Exercise the real Groq SDK over an in-memory HTTP transport only."""

import json

import httpx
import pytest
from groq import Groq
from pydantic import SecretStr

from cyberforge.llm.contracts import (
    Contract,
    ErrorCategory,
    GenerationError,
    GenerationParameters,
    GenerationRequest,
    Provider,
)
from cyberforge.llm.groq_provider import GroqProvider


class Message(Contract):
    message: str


def request():
    return GenerationRequest(
        prompt="Synthetic input",
        synthetic=True,
        provider=Provider.GROQ,
        model="openai/gpt-oss-120b",
        parameters=GenerationParameters(thinking="low"),
    )


def adapter(handler):
    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        assert kwargs["timeout"] == 30
        assert kwargs["base_url"] == "https://api.groq.com"
        return Groq(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler))
        )

    return GroqProvider(SecretStr("synthetic-test-key"), client_factory=factory)


def payload(content='{"message":"fixture"}', finish="stop", refusal=None):
    return {
        "id": "fixture",
        "object": "chat.completion",
        "created": 0,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "refusal": refusal,
                },
                "finish_reason": finish,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
    }


def test_strict_schema_reasoning_and_usage(caplog):
    caplog.set_level("DEBUG")
    captured = []

    def handler(req):
        captured.append(req)
        return httpx.Response(200, json=payload())

    response = adapter(handler).generate(request(), Message.model_json_schema())
    body = json.loads(captured[0].content)
    assert body["response_format"]["json_schema"]["strict"] is True
    assert (
        body["response_format"]["json_schema"]["schema"]["additionalProperties"]
        is False
    )
    assert body["reasoning_effort"] == "low"
    assert "max_completion_tokens" not in body
    assert response.usage.input_tokens == 10
    assert response.actual_model == "openai/gpt-oss-120b"
    assert "synthetic-test-key" not in caplog.text
    assert "Synthetic input" not in caplog.text


def test_explicit_large_output_limit_is_forwarded():
    captured = []

    def handler(req):
        captured.append(json.loads(req.content))
        return httpx.Response(200, json=payload())

    value = request().model_copy(
        update={"parameters": GenerationParameters(max_output_tokens=50000)}
    )
    adapter(handler).generate(value, Message.model_json_schema())
    assert captured[0]["max_completion_tokens"] == 50000


@pytest.mark.parametrize(
    "status,category",
    [
        (401, ErrorCategory.AUTHORIZATION),
        (403, ErrorCategory.AUTHORIZATION),
        (400, ErrorCategory.REQUEST),
        (404, ErrorCategory.REQUEST),
        (429, ErrorCategory.RATE_LIMIT),
        (503, ErrorCategory.UNAVAILABLE),
    ],
)
def test_one_sdk_attempt_and_sanitized_errors(status, category, caplog):
    caplog.set_level("DEBUG")
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            status,
            json={"error": {"message": "private-secret"}},
            headers={"Retry-After": "7"},
        )

    with pytest.raises(GenerationError) as caught:
        adapter(handler).generate(request(), None)
    assert caught.value.category == category
    assert caught.value.retry_after == 7
    assert caught.value.__context__ is None
    assert "private-secret" not in str(caught.value)
    assert "private-secret" not in caplog.text
    assert "synthetic-test-key" not in caplog.text
    assert len(calls) == 1


def test_timeout_is_normalized():
    def handler(req):
        raise httpx.ReadTimeout("private-secret", request=req)

    with pytest.raises(GenerationError, match="timeout"):
        adapter(handler).generate(request(), None)


@pytest.mark.parametrize(
    "finish,refusal,category",
    [
        ("content_filter", None, ErrorCategory.SAFETY),
        ("stop", "refused", ErrorCategory.SAFETY),
        ("length", None, ErrorCategory.VALIDATION),
    ],
)
def test_refusals_and_truncation(finish, refusal, category):
    provider = adapter(
        lambda req: httpx.Response(200, json=payload(finish=finish, refusal=refusal))
    )
    with pytest.raises(GenerationError) as caught:
        provider.generate(request(), None)
    assert caught.value.category == category


def test_missing_credentials_never_initializes_sdk():
    def forbidden(**kwargs):
        pytest.fail("SDK initialized without key")

    with pytest.raises(GenerationError, match="missing_credentials"):
        GroqProvider(None, client_factory=forbidden).generate(request(), None)
