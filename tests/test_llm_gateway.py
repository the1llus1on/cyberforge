"""Offline policy tests with deterministic responses, clocks and wait functions."""

import socket
from pathlib import Path

import pytest
from pydantic import Field, SecretStr

from cyberforge.llm.config import GatewayConfig, RateLimits, load_config
from cyberforge.llm.contracts import (
    Contract,
    ErrorCategory,
    GenerationError,
    GenerationParameters,
    GenerationRequest,
    Provider,
    ProviderResponse,
)
from cyberforge.llm.gateway import GenerationFailure, LLMGateway
from cyberforge.llm.limits import RateLimiter
from cyberforge.llm.mock import MockLLMProvider
from cyberforge.llm.provider_errors import normalize_error, retry_after_seconds
from cyberforge.llm.schemas import groq_strict_schema


class Message(Contract):
    message: str


def request(**updates):
    return GenerationRequest(prompt="Synthetic fixture", synthetic=True, **updates)


def gateway(config=None, responses=None, backup=None):
    primary = MockLLMProvider(responses)
    backup = backup or MockLLMProvider()
    waits = []
    now = [42.0]

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    instance = LLMGateway(
        config or GatewayConfig(),
        {Provider.MOCK: primary, Provider.GEMINI: primary, Provider.GROQ: backup},
        sleep=sleep,
        clock=lambda: now[0],
        jitter=lambda: 0.25,
    )
    return instance, primary, backup, waits


def test_offline_mock_is_reproducible_and_does_not_connect(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline mock attempted network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    instance, *_ = gateway()
    assert instance.generate(request()).text == instance.generate(request()).text
    structured = instance.generate(
        request(operation="structured", schema_version="message-v1"), Message
    )
    assert structured.structured.message == "Синтетичний приклад"
    assert structured.telemetry.local_validation == "passed"


@pytest.mark.parametrize("category", list(ErrorCategory))
def test_retry_and_fallback_allowlists(category):
    instance, primary, backup, waits = gateway(
        GatewayConfig(max_retries=1, fallback_to_groq=True),
        [GenerationError(category), GenerationError(category)],
    )
    req = request(provider=Provider.GEMINI, model="gemini-3.8-flash")
    if category in {ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE}:
        result = instance.generate(req)
        assert result.telemetry.fallback
        assert result.telemetry.provider == Provider.GROQ
        assert result.telemetry.requested_model == req.model
        assert backup.calls == 1
    else:
        with pytest.raises(GenerationFailure) as caught:
            instance.generate(req)
        assert caught.value.category == category
        assert backup.calls == 0
    retried = category in {
        ErrorCategory.TIMEOUT,
        ErrorCategory.UNAVAILABLE,
        ErrorCategory.RATE_LIMIT,
    }
    assert primary.calls == (2 if retried else 1)
    assert waits == ([1.25] if retried else [])


def test_retry_after_and_success_metadata():
    instance, primary, _, waits = gateway(
        responses=[GenerationError(ErrorCategory.RATE_LIMIT, 5)]
    )
    result = instance.generate(request())
    assert waits == [5]
    assert primary.calls == 2
    assert result.telemetry.retry_count == 1
    assert result.telemetry.usage.input_tokens == 8


def test_retry_after_above_wait_budget_is_not_shortened():
    instance, primary, _, waits = gateway(
        responses=[GenerationError(ErrorCategory.RATE_LIMIT, 1000)]
    )
    with pytest.raises(GenerationFailure):
        instance.generate(request())
    assert primary.calls == 1
    assert waits == []


def test_retry_after_blocks_followup_requests_across_models():
    now = [0.0]
    provider = MockLLMProvider([GenerationError(ErrorCategory.RATE_LIMIT, 120)])
    instance = LLMGateway(
        GatewayConfig(max_retries=0, fallback_to_groq=True),
        {Provider.GEMINI: provider},
        clock=lambda: now[0],
    )
    for model in ["gemini-3.8-flash", "gemini-3.5-flash-lite"]:
        with pytest.raises(GenerationFailure, match="rate_limit"):
            instance.generate(request(provider=Provider.GEMINI, model=model))
    assert provider.calls == 1
    now[0] = 121
    instance.generate(request(provider=Provider.GEMINI, model="gemini-3.5-flash-lite"))
    assert provider.calls == 2


def test_concurrent_reservations_do_not_exceed_budget():
    from concurrent.futures import ThreadPoolExecutor

    limiter = RateLimiter({"mock": RateLimits(rpm=1)}, lambda: 42)

    def reserve(_):
        try:
            limiter.reserve(request())
            return True
        except GenerationError:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(reserve, range(12))) == 1


def test_structured_schema_is_included_in_token_budget():
    instance, provider, *_ = gateway(
        GatewayConfig(limits={"mock": RateLimits(tpm=8000)})
    )

    class LargeSchema(Contract):
        message: str = Field(description="Synthetic schema description. " * 400)

    with pytest.raises(GenerationFailure, match="budget_exhausted"):
        instance.generate(
            request(operation="structured", schema_version="large-v1"), LargeSchema
        )
    assert provider.calls == 0


def test_non_json_pydantic_schema_is_rejected_before_transport():
    from collections.abc import Callable

    class NonJSONSchema(Contract):
        callback: Callable[[], str]

    instance, provider, *_ = gateway()
    with pytest.raises(GenerationFailure, match="unsupported_schema"):
        instance.generate(
            request(operation="structured", schema_version="v1"), NonJSONSchema
        )
    assert provider.calls == 0


@pytest.mark.parametrize("key", ["mock", "mock:mock-v1"])
@pytest.mark.parametrize("field", ["rpm", "rpd", "tpm", "tpd"])
def test_both_budget_levels_and_all_dimensions(key, field):
    now = [0]
    tokens = len(b"Synthetic fixture")
    limit = 1 if field in {"rpm", "rpd"} else tokens
    limiter = RateLimiter({key: RateLimits(**{field: limit})}, lambda: now[0])
    limiter.reserve(request())
    with pytest.raises(GenerationError, match="budget_exhausted"):
        limiter.reserve(request())
    now[0] = 86401
    limiter.reserve(request())


def test_failed_attempt_is_charged_and_cannot_fallback_on_budget():
    instance, primary, backup, _ = gateway(
        GatewayConfig(limits={"gemini": RateLimits(rpm=1)}, fallback_to_groq=True),
        [GenerationError(ErrorCategory.UNAVAILABLE)],
    )
    with pytest.raises(GenerationFailure, match="budget_exhausted"):
        instance.generate(request(provider=Provider.GEMINI, model="gemini-3.8-flash"))
    assert primary.calls == 1
    assert backup.calls == 0


@pytest.mark.parametrize(
    "text", ["not json", '{"message":1}', '{"message":"x","extra":1}']
)
def test_local_validation_is_mandatory_and_never_retried(text):
    instance, primary, backup, _ = gateway(responses=[ProviderResponse(text=text)])
    with pytest.raises(GenerationFailure) as caught:
        instance.generate(request(operation="structured", schema_version="v1"), Message)
    assert caught.value.telemetry.local_validation == "failed"
    assert caught.value.category == ErrorCategory.VALIDATION
    assert primary.calls == 1
    assert backup.calls == 0


def test_model_and_thinking_validation_happens_before_transport():
    instance, primary, *_ = gateway()
    for req in [
        request(provider=Provider.GEMINI, model="unapproved"),
        request(
            provider=Provider.GEMINI,
            model="gemini-3.8-flash",
            parameters=GenerationParameters(thinking="minimal"),
        ),
    ]:
        with pytest.raises(GenerationFailure, match="configuration"):
            instance.generate(req)
    assert primary.calls == 0


def test_env_precedence_no_interpolation_and_no_secret_export(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "GOOGLE_API_KEY=private-file-value\nGROQ_API_KEY=${GOOGLE_API_KEY}\n"
    )
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = load_config(env, {"GOOGLE_API_KEY": "private-env-value"})
    assert config.google_api_key.get_secret_value() == "private-env-value"
    assert config.groq_api_key.get_secret_value() == "${GOOGLE_API_KEY}"
    assert "private" not in repr(config)
    assert "private" not in config.model_dump_json()
    assert "private" not in repr(GenerationRequest(prompt="private", synthetic=True))
    empty = load_config(env, {"GOOGLE_API_KEY": ""})
    assert empty.google_api_key is None


def test_missing_file_is_offline_default_and_bad_config_is_sanitized(tmp_path):
    assert load_config(tmp_path / "missing", {}).provider == Provider.MOCK
    with pytest.raises(GenerationError) as caught:
        load_config(tmp_path / "missing", {"CYBERFORGE_LLM_PROVIDER": "private-value"})
    assert "private-value" not in str(caught.value)


def test_quota_configuration_typos_fail_closed(tmp_path):
    with pytest.raises(GenerationError, match="configuration"):
        load_config(
            tmp_path / "missing",
            {
                "CYBERFORGE_LLM_LIMITS": '{"groqq":{"rpm":1}}',
            },
        )


def test_invalid_model_is_not_copied_into_telemetry():
    instance, *_ = gateway()
    with pytest.raises(GenerationFailure) as caught:
        instance.generate(request(model="private-misconfigured-value"))
    assert "private" not in caught.value.telemetry.model_dump_json()


def test_metadata_does_not_include_prompts_responses_or_keys():
    instance, *_ = gateway(GatewayConfig(google_api_key=SecretStr("private-key")))
    result = instance.generate(
        GenerationRequest(prompt="private-prompt", synthetic=True)
    )
    serialized = result.model_dump_json()
    assert "private" not in serialized
    assert result.text not in serialized
    assert result.telemetry.elapsed_seconds == 0


def test_telemetry_sink_cannot_leak_errors_or_repeat_generation():
    class FailingSink:
        def record(self, telemetry):
            raise RuntimeError("private-sink-data")

    provider = MockLLMProvider()
    instance = LLMGateway(
        GatewayConfig(), {Provider.MOCK: provider}, sink=FailingSink()
    )
    assert instance.generate(request()).telemetry.status == "success"
    assert provider.calls == 1


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": {"x": {"type": "string"}}},
        {
            "type": "object",
            "properties": {"x": {"anyOf": [{"type": "string"}]}},
            "required": ["x"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {"x": {"type": "string", "pattern": "x"}},
            "required": ["x"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {"x": {"$ref": "#/$defs/X"}},
            "required": ["x"],
            "additionalProperties": False,
            "$defs": {"X": {"$ref": "#/$defs/X"}},
        },
    ],
)
def test_groq_rejects_unsupported_schema(schema):
    with pytest.raises(GenerationError, match="unsupported_schema"):
        groq_strict_schema(schema)


def test_groq_preserves_supported_schema():
    transformed = groq_strict_schema(Message.model_json_schema())
    assert transformed["additionalProperties"] is False
    assert transformed["required"] == ["message"]
    assert transformed["properties"]["message"] == {"type": "string"}


def test_status_sanitization_and_retry_header():
    class SDKError(Exception):
        status_code = 403

    error = normalize_error(SDKError("private-secret"))
    assert str(error) == "authorization"
    assert error.__context__ is None
    assert retry_after_seconds("5") == 5
    assert retry_after_seconds("nan") is None
    assert retry_after_seconds("invalid") is None


def test_env_is_git_ignored():
    import subprocess

    result = subprocess.run(["git", "check-ignore", ".env"], capture_output=True)
    assert result.returncode == 0
    assert Path(".env.example").exists()
