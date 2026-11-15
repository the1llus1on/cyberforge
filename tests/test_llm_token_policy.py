"""Opt-in budgets and metadata-only failures, never live transport."""

import json

import httpx
import pytest
from groq import Groq
from pydantic import SecretStr, ValidationError

from cyberforge.agents.contracts import EmailInputV1
from cyberforge.agents.demo import email_payload
from cyberforge.agents.email_live_check import run_check
from cyberforge.llm.config import GatewayConfig, RateLimits, load_config
from cyberforge.llm.contracts import GenerationParameters, GenerationRequest, Provider
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.groq_provider import GroqProvider
from cyberforge.llm.limits import RateLimiter


def test_limits_are_optional_and_have_no_application_ceiling(tmp_path):
    config = load_config(tmp_path / "absent.env", {})
    assert config.parameters.max_output_tokens is None
    assert config.email_max_output_tokens is None and config.limits == {}
    assert RateLimits().model_dump() == dict(rpm=None, tpm=None, rpd=None, tpd=None)
    for value in (1, 8193, 1000000):
        assert GenerationParameters(max_output_tokens=value).max_output_tokens == value
        assert (
            GatewayConfig(email_max_output_tokens=value).email_max_output_tokens
            == value
        )
    with pytest.raises(ValidationError):
        GenerationParameters(max_output_tokens=0)
    request = GenerationRequest(
        prompt="X" * 24000,
        synthetic=True,
        parameters=GenerationParameters(max_output_tokens=1000000),
    )
    limiter = RateLimiter({})
    for _ in range(110):
        limiter.reserve(request)
    assert not limiter._entries


@pytest.mark.parametrize(
    "code,kind",
    [
        ("context_length_exceeded", "context_limit"),
        ("max_completion_tokens_exceeded", "output_limit"),
        ("json_validate_failed", "structured_output"),
        ("invalid_json_schema", "structured_output"),
        ("invalid_request", "invalid_request"),
        ("private-secret", "invalid_request"),
        (None, None),
    ],
)
@pytest.mark.parametrize("output_limit", [None, 4096])
def test_real_sdk_initial_and_refinement_requests(
    code, kind, output_limit, capsys, caplog
):
    caplog.set_level("DEBUG")
    captured = []
    first = None

    def handler(request):
        nonlocal first
        body = json.loads(request.content)
        captured.append(body)
        data = json.loads(
            body["messages"][0]["content"]
            .split("BEGIN_UNTRUSTED_JSON\n")[1]
            .split("\nEND_UNTRUSTED_JSON")[0]
        )
        token = data.pop("context_token")
        previous = data.pop("previous", None)
        if previous is not None:
            assert previous == first
            if code is not None:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "type": "invalid_request_error",
                            "code": code,
                            "message": "private-secret",
                            "failed_generation": "private-secret",
                        }
                    },
                )
        source = EmailInputV1.model_validate_json(json.dumps(data))
        slots = email_payload(source)
        slots["context_token"] = token
        if first is None:
            first = slots
        else:
            slots["main"]["body_text"] = "Скорочений навчальний текст."
            slots["main"]["subject"] = "Небажана зміна теми"
            slots["background"][0]["subject"] = "Небажана зміна фону"
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 0,
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": json.dumps(slots)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1452,
                    "completion_tokens": 742,
                    "total_tokens": 2194,
                },
            },
        )

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return Groq(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler))
        )

    provider = GroqProvider(SecretStr("fixture-key"), client_factory=factory)
    gateway = LLMGateway(
        GatewayConfig(
            provider=Provider.GROQ,
            model="openai/gpt-oss-120b",
            max_retries=0,
            parameters=GenerationParameters(
                thinking="low", max_output_tokens=output_limit
            ),
        ),
        {Provider.GROQ: provider},
    )
    assert run_check(gateway) is (code is None)
    assert len(captured) == 2
    assert captured[0]["response_format"] == captured[1]["response_format"]
    assert captured[1]["reasoning_effort"] == "low"
    assert captured[1]["response_format"]["json_schema"]["strict"] is True
    if output_limit is None:
        assert all("max_completion_tokens" not in body for body in captured)
    else:
        assert all(body["max_completion_tokens"] == output_limit for body in captured)
    output = capsys.readouterr().out
    records = [json.loads(line) for line in output.splitlines()]
    refined = records[1]
    assert records[0]["contract_valid"] is True
    if code is None:
        assert refined["protected_fields_preserved"] is True
    else:
        telemetry = refined["telemetry"][0]
        assert telemetry["usage"]["output_tokens"] is None
        assert telemetry["provider_diagnostics"] == {
            "http_status": 400,
            "error_type": "invalid_request_error",
            "error_code": code if code != "private-secret" else None,
            "kind": kind,
        }
    for private in ("private-secret", "fixture-key", "body_text", "failed_generation"):
        assert private not in output and private not in caplog.text
