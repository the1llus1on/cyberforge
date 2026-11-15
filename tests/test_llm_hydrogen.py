"""Hydrogen requests and explicit one-hop backup policy, entirely offline."""

import json

import httpx
import pytest
from google import genai
from pydantic import Field, SecretStr, ValidationError

from cyberforge.llm import diagnostics
from cyberforge.llm.config import BackupConfig, GatewayConfig, RateLimits, load_config
from cyberforge.llm.contracts import (
    Contract,
    EmailArtifactV1,
    ErrorCategory,
    GenerationError,
    GenerationParameters,
    GenerationRequest,
    Provider,
    ProviderResponse,
    WebArtifactV1,
)
from cyberforge.llm.factory import configured_request, create_gateway
from cyberforge.llm.gateway import GenerationFailure, LLMGateway
from cyberforge.llm.gemini_provider import GeminiProvider
from cyberforge.llm.groq_provider import GroqProvider

HYDROGEN = "gemini-4-hydrogen"
GROQ = "openai/gpt-oss-120b"


class Recorder:
    def __init__(self, response="Synthetic result"):
        self.response = response
        self.requests = []
        self.schemas = []

    def generate(self, request, schema):
        self.requests.append(request)
        self.schemas.append(schema)
        if isinstance(self.response, GenerationError):
            raise self.response
        return ProviderResponse(text=self.response, actual_model=request.model)


def cloud_config(**updates):
    return GatewayConfig(
        provider=Provider.GROQ,
        model=GROQ,
        max_retries=0,
        backup=BackupConfig(
            provider=Provider.GEMINI, model=HYDROGEN, enabled=True, access_verified=True
        ),
        **updates,
    )


def primary_request(**updates):
    return GenerationRequest(
        prompt="Synthetic fixture",
        synthetic=True,
        provider=Provider.GROQ,
        model=GROQ,
        **updates,
    )


def google_sdk(calls, text="Synthetic result", status="completed"):
    def handler(req):
        calls.append((req, json.loads(req.content)))
        return httpx.Response(
            200,
            json={
                "status": status,
                "model": HYDROGEN,
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": text}],
                    }
                ],
                "usage": {
                    "total_input_tokens": 12,
                    "total_output_tokens": 5,
                    "total_thought_tokens": 2,
                },
                **(
                    {"continuation_token": "synthetic-token"}
                    if status == "requires_continuation"
                    else {}
                ),
            },
        )

    def factory(**kwargs):
        assert kwargs["vertexai"] is False
        assert kwargs["http_options"].api_version == "v1"
        assert kwargs["http_options"].retry_options.attempts == 1
        kwargs["http_options"] = kwargs["http_options"].model_copy(
            update={
                "httpx_client": httpx.Client(transport=httpx.MockTransport(handler)),
            }
        )
        return genai.Client(**kwargs)

    return GeminiProvider(SecretStr("synthetic-key"), client_factory=factory)


@pytest.mark.parametrize("thinking", ["low", "medium", "high", "xhigh"])
@pytest.mark.parametrize("structured", [False, True])
def test_hydrogen_sdk_configuration(thinking, structured, caplog, monkeypatch):
    caplog.set_level("DEBUG")
    monkeypatch.setenv("GOOGLE_GENAI_DEBUG", "1")
    calls = []
    req = GenerationRequest(
        prompt="Synthetic fixture",
        synthetic=True,
        provider=Provider.GEMINI,
        model=HYDROGEN,
        parameters=GenerationParameters(
            temperature=0.65,
            thinking=thinking,
            max_output_tokens=123,
            timeout_seconds=13,
        ),
    )
    schema = (
        {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
            "additionalProperties": False,
        }
        if structured
        else None
    )
    result = google_sdk(calls).generate(req, schema)
    assert len(calls) == 1
    http_request, body = calls[0]
    assert http_request.url.host == "generativelanguage.googleapis.com"
    assert http_request.url.path == "/v1/interactions"
    assert body["model"] == HYDROGEN
    assert body["store"] is body["background"] is body["stream"] is False
    assert not {"previous_interaction_id", "tools", "continuation_token"} & body.keys()
    assert body["generation_config"] == {
        "thinking_level": thinking,
        "max_output_tokens": 123,
        "thinking_summaries": "none",
    }
    assert "temperature" not in body["generation_config"]
    assert "top_p" not in body["generation_config"]
    assert "top_k" not in body["generation_config"]
    if structured:
        assert body["response_format"]["schema"] == schema
    else:
        assert "response_format" not in body
    assert result.actual_model == HYDROGEN
    assert result.usage.input_tokens == 12
    assert "Synthetic fixture" not in caplog.text
    assert "synthetic-key" not in caplog.text


@pytest.mark.parametrize(
    "provider,model,thinking",
    [
        (Provider.GEMINI, HYDROGEN, "minimal"),
        (Provider.GEMINI, "gemini-3.8-flash", "xhigh"),
        (Provider.GEMINI, "gemini-3.5-flash-lite", "xhigh"),
        (Provider.GROQ, GROQ, "xhigh"),
        (Provider.MOCK, "mock-v1", "xhigh"),
    ],
)
def test_exclusive_thinking_validation(provider, model, thinking):
    recorder = Recorder()
    gateway = LLMGateway(GatewayConfig(), {provider: recorder})
    with pytest.raises(GenerationFailure, match="configuration"):
        gateway.generate(
            GenerationRequest(
                prompt="Synthetic",
                synthetic=True,
                provider=provider,
                model=model,
                parameters=GenerationParameters(thinking=thinking),
            )
        )
    assert recorder.requests == []


def test_config_offline_default_and_explicit_groq_primary(tmp_path):
    config = load_config(tmp_path / "missing", {})
    assert config.provider == Provider.MOCK and config.backup is None
    assert (
        create_gateway(config)
        .generate(
            GenerationRequest(
                prompt="Synthetic",
                synthetic=True,
            )
        )
        .telemetry.provider
        == Provider.MOCK
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CYBERFORGE_LLM_PROVIDER=groq\nCYBERFORGE_LLM_MODEL=openai/gpt-oss-120b\n"
        'CYBERFORGE_LLM_BACKUP={"provider":"gemini","model":"gemini-4-hydrogen"}\n'
    )
    config = load_config(env_file, {})
    req = configured_request(config, prompt="Synthetic", synthetic=True)
    assert req.provider == Provider.GROQ and req.model == GROQ
    assert config.backup.enabled is False
    assert config.backup.access_verified is False


@pytest.mark.parametrize(
    "backup",
    [
        {"provider": "gemini", "model": HYDROGEN, "enabled": True},
        {"provider": "gemini", "model": "unapproved"},
        {"provider": "mock", "model": "mock-v1"},
    ],
)
def test_invalid_or_unverified_backup_fails_closed(backup):
    with pytest.raises(ValidationError):
        GatewayConfig(provider=Provider.GROQ, model=GROQ, backup=backup)


def test_legacy_conflict_and_cycles_fail_closed():
    with pytest.raises(ValidationError):
        GatewayConfig(
            fallback_to_groq=True,
            backup=BackupConfig(provider=Provider.GEMINI, model=HYDROGEN),
        )
    with pytest.raises(ValidationError):
        GatewayConfig(
            provider=Provider.GROQ,
            model=GROQ,
            backup=BackupConfig(
                provider=Provider.GROQ, model=GROQ, enabled=True, access_verified=True
            ),
        )
    with pytest.raises(ValidationError):
        GatewayConfig(backup=cloud_config().backup)


@pytest.mark.parametrize("category", [ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE])
@pytest.mark.parametrize("thinking", [None, "low", "medium", "high"])
def test_groq_hydrogen_fallback_metadata(category, thinking):
    primary, backup = Recorder(GenerationError(category)), Recorder()
    original = primary_request(
        parameters=GenerationParameters(thinking=thinking, temperature=0.65)
    )
    result = LLMGateway(
        cloud_config(),
        {
            Provider.GROQ: primary,
            Provider.GEMINI: backup,
        },
    ).generate(original)
    assert len(primary.requests) == len(backup.requests) == 1
    sent = backup.requests[0]
    assert sent.model == HYDROGEN and sent.provider == Provider.GEMINI
    assert sent.parameters.thinking == thinking and sent.parameters.temperature is None
    assert original.parameters.temperature == 0.65
    assert result.telemetry.requested_provider == Provider.GROQ
    assert result.telemetry.requested_model == GROQ
    assert result.telemetry.provider == Provider.GEMINI
    assert result.telemetry.effective_model == result.telemetry.actual_model == HYDROGEN
    assert result.telemetry.requested_parameters == original.parameters
    assert result.telemetry.effective_parameters == sent.parameters


@pytest.mark.parametrize(
    "category",
    [
        c
        for c in ErrorCategory
        if c not in {ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE}
    ],
)
def test_new_fallback_retains_denylist(category):
    primary, backup = Recorder(GenerationError(category)), Recorder()
    with pytest.raises(GenerationFailure) as caught:
        LLMGateway(
            cloud_config(), {Provider.GROQ: primary, Provider.GEMINI: backup}
        ).generate(primary_request())
    assert caught.value.category == category
    assert caught.value.telemetry.fallback is False
    assert backup.requests == []


def test_no_second_hop_and_separate_backup_budget():
    primary = Recorder(GenerationError(ErrorCategory.UNAVAILABLE))
    backup = Recorder(GenerationError(ErrorCategory.UNAVAILABLE))
    with pytest.raises(GenerationFailure, match="unavailable"):
        LLMGateway(
            cloud_config(), {Provider.GROQ: primary, Provider.GEMINI: backup}
        ).generate(primary_request())
    assert len(primary.requests) == len(backup.requests) == 1
    backup = Recorder()
    with pytest.raises(GenerationFailure, match="budget_exhausted"):
        LLMGateway(
            cloud_config(limits={"gemini": RateLimits(tpm=1)}),
            {
                Provider.GROQ: primary,
                Provider.GEMINI: backup,
            },
        ).generate(primary_request())
    assert backup.requests == []


def test_local_primary_budget_and_missing_keys_do_not_fallback():
    primary, backup = Recorder(), Recorder()
    with pytest.raises(GenerationFailure, match="budget_exhausted"):
        LLMGateway(
            cloud_config(limits={"groq": RateLimits(tpm=1)}),
            {
                Provider.GROQ: primary,
                Provider.GEMINI: backup,
            },
        ).generate(primary_request())
    assert primary.requests == backup.requests == []
    with pytest.raises(GenerationFailure, match="missing_credentials"):
        LLMGateway(
            cloud_config(),
            {
                Provider.GROQ: GroqProvider(None),
                Provider.GEMINI: backup,
            },
        ).generate(primary_request())
    assert backup.requests == []


@pytest.mark.parametrize("access_verified", [False, True])
def test_disabled_backup_never_runs(access_verified):
    config = GatewayConfig(
        provider=Provider.GROQ,
        model=GROQ,
        max_retries=0,
        backup=BackupConfig(
            provider=Provider.GEMINI, model=HYDROGEN, access_verified=access_verified
        ),
    )
    backup = Recorder()
    with pytest.raises(GenerationFailure, match="unavailable"):
        LLMGateway(
            config,
            {
                Provider.GROQ: Recorder(GenerationError(ErrorCategory.UNAVAILABLE)),
                Provider.GEMINI: backup,
            },
        ).generate(primary_request())
    assert backup.requests == []


@pytest.mark.parametrize(
    "provider,model",
    [(Provider.MOCK, "mock-v1"), (Provider.GEMINI, "gemini-3.5-flash-lite")],
)
def test_explicit_primary_match_required_and_mock_stays_offline(provider, model):
    recorder = Recorder(GenerationError(ErrorCategory.UNAVAILABLE))
    with pytest.raises(GenerationFailure, match="unavailable") as caught:
        LLMGateway(cloud_config(), {provider: recorder}).generate(
            GenerationRequest(
                prompt="Synthetic",
                synthetic=True,
                provider=provider,
                model=model,
            )
        )
    assert len(recorder.requests) == 1
    assert caught.value.telemetry.fallback is False


def artifact(output_type, valid):
    context = {
        "schema_version": "scenario-context-v1",
        "organization": "Synthetic",
        "sender_name": "Synthetic",
        "premise": "Synthetic",
        "internal_resource_id": "resource-1" if valid else "../invalid",
    }
    if output_type is EmailArtifactV1:
        return {
            "schema_version": "email-artifact-v1",
            "context": context,
            "subject": "Synthetic",
            "body_text": "Synthetic",
        }
    return {
        "schema_version": "web-artifact-v1",
        "context": context,
        "heading": "Synthetic",
        "body_text": "Synthetic",
        "action_label": "Continue",
    }


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
@pytest.mark.parametrize("valid", [True, False])
def test_structured_fallback_preserves_original_validation_and_projection(
    output_type, valid
):
    calls = []
    primary = Recorder(GenerationError(ErrorCategory.UNAVAILABLE))
    gateway = LLMGateway(
        cloud_config(),
        {
            Provider.GROQ: primary,
            Provider.GEMINI: google_sdk(
                calls, json.dumps(artifact(output_type, valid))
            ),
        },
    )
    req = primary_request(operation="structured", schema_version="artifact-v1")
    if valid:
        result = gateway.generate(req, output_type)
        telemetry = result.telemetry
        assert result.structured.context.internal_resource_id == "resource-1"
        assert telemetry.local_validation == "passed"
    else:
        with pytest.raises(GenerationFailure, match="validation") as caught:
            gateway.generate(req, output_type)
        telemetry = caught.value.telemetry
        assert telemetry.local_validation == "failed"
    assert len(calls) == 1
    assert primary.schemas[0]["properties"]["context"]["properties"][
        "internal_resource_id"
    ] == {"type": "string"}
    assert calls[0][1]["response_format"]["schema"] == output_type.model_json_schema()
    assert telemetry.schema_projection is None
    assert (
        telemetry.requested_provider == Provider.GROQ
        and telemetry.provider == Provider.GEMINI
    )


@pytest.mark.parametrize("output_type", [EmailArtifactV1, WebArtifactV1])
def test_invalid_primary_artifact_never_falls_back(output_type):
    primary = Recorder(json.dumps(artifact(output_type, False)))
    backup = Recorder()
    with pytest.raises(GenerationFailure, match="validation") as caught:
        LLMGateway(
            cloud_config(), {Provider.GROQ: primary, Provider.GEMINI: backup}
        ).generate(
            primary_request(operation="structured", schema_version="artifact-v1"),
            output_type,
        )
    assert backup.requests == []
    assert caught.value.telemetry.fallback is False
    assert (
        caught.value.telemetry.schema_projection == "groq-artifact-v1-local-resource-id"
    )


def test_unsupported_primary_schema_does_not_invoke_either_provider():
    class Unsupported(Contract):
        identifier: str = Field(pattern="^unsupported$")

    primary, backup = Recorder(), Recorder()
    with pytest.raises(GenerationFailure, match="unsupported_schema"):
        LLMGateway(
            cloud_config(), {Provider.GROQ: primary, Provider.GEMINI: backup}
        ).generate(
            primary_request(operation="structured", schema_version="v1"), Unsupported
        )
    assert primary.requests == backup.requests == []


def test_legacy_hydrogen_xhigh_fallback_maps_high_and_restores_temperature():
    backup = Recorder()
    req = GenerationRequest(
        prompt="Synthetic",
        synthetic=True,
        provider=Provider.GEMINI,
        model=HYDROGEN,
        parameters=GenerationParameters(thinking="xhigh", temperature=0.65),
    )
    result = LLMGateway(
        GatewayConfig(fallback_to_groq=True, max_retries=0),
        {
            Provider.GEMINI: Recorder(GenerationError(ErrorCategory.UNAVAILABLE)),
            Provider.GROQ: backup,
        },
    ).generate(req)
    assert backup.requests[0].parameters.thinking == "high"
    assert backup.requests[0].parameters.temperature == 0.65
    assert result.telemetry.requested_parameters.thinking == "xhigh"
    assert req.parameters.thinking == "xhigh"


def test_hydrogen_continuation_never_runs():
    calls = []
    with pytest.raises(GenerationError, match="validation"):
        google_sdk(calls, status="requires_continuation").generate(
            GenerationRequest(
                prompt="Synthetic",
                synthetic=True,
                provider=Provider.GEMINI,
                model=HYDROGEN,
            ),
            None,
        )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "status,category",
    [
        (401, "authorization"),
        (403, "authorization"),
        (429, "rate_limit"),
        (503, "unavailable"),
    ],
)
def test_hydrogen_sdk_errors_have_no_retries(status, category, caplog):
    calls = []

    def factory(**kwargs):
        def handler(req):
            calls.append(req)
            return httpx.Response(
                status, json={"error": {"code": status, "message": "synthetic-private"}}
            )

        kwargs["http_options"] = kwargs["http_options"].model_copy(
            update={
                "httpx_client": httpx.Client(transport=httpx.MockTransport(handler))
            }
        )
        return genai.Client(**kwargs)

    with pytest.raises(GenerationError, match=category):
        GeminiProvider(SecretStr("synthetic-key"), client_factory=factory).generate(
            GenerationRequest(
                prompt="Synthetic",
                synthetic=True,
                provider=Provider.GEMINI,
                model=HYDROGEN,
            ),
            None,
        )
    assert len(calls) == 1
    assert "synthetic-private" not in caplog.text


def test_bounded_retry_budget_is_shared_by_new_fallback_path():
    primary = Recorder(GenerationError(ErrorCategory.UNAVAILABLE))

    class Backup(Recorder):
        def generate(self, req, schema):
            self.response = (
                "Synthetic result"
                if self.requests
                else GenerationError(ErrorCategory.TIMEOUT)
            )
            return super().generate(req, schema)

    backup = Backup()
    now = [0.0]
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    config = cloud_config().model_copy(update={"max_retries": 1})
    result = LLMGateway(
        config,
        {Provider.GROQ: primary, Provider.GEMINI: backup},
        clock=lambda: now[0],
        sleep=sleep,
        jitter=lambda: 0,
    ).generate(primary_request())
    assert len(primary.requests) == len(backup.requests) == 2
    assert waits == [1, 1] and result.telemetry.retry_count == 2


def test_unverified_backup_cannot_run_even_after_unvalidated_copy():
    backup = Recorder()
    config = cloud_config().model_copy(
        update={
            "backup": BackupConfig(provider=Provider.GEMINI, model=HYDROGEN).model_copy(
                update={"enabled": True}
            )
        }
    )
    with pytest.raises(GenerationFailure, match="unavailable"):
        LLMGateway(
            config,
            {
                Provider.GROQ: Recorder(GenerationError(ErrorCategory.UNAVAILABLE)),
                Provider.GEMINI: backup,
            },
        ).generate(primary_request())
    assert backup.requests == []


@pytest.mark.parametrize(
    "category",
    [ErrorCategory.UNAVAILABLE, ErrorCategory.AUTHORIZATION, ErrorCategory.RATE_LIMIT],
)
def test_hydrogen_cli_normalized_failures_without_network(
    monkeypatch, capsys, category
):
    monkeypatch.setattr(diagnostics, "load_config", lambda path: cloud_config())
    calls = []

    class Diagnostic:
        def generate(self, req):
            calls.append(req)
            raise GenerationError(category)

    monkeypatch.setattr(diagnostics, "create_gateway", lambda config: Diagnostic())
    assert (
        diagnostics.main(["--live", "--provider", "gemini", "--model", HYDROGEN]) == 1
    )
    assert json.loads(capsys.readouterr().out)["outcome"] == category.value
    assert len(calls) == 1


def test_hydrogen_diagnostic_guard_and_single_mocked_execution(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("disabled CLI read configuration")

    monkeypatch.setattr(diagnostics, "load_config", forbidden)
    with pytest.raises(SystemExit) as caught:
        diagnostics.main(["--provider", "gemini", "--model", HYDROGEN])
    assert caught.value.code == 2
    monkeypatch.setattr(diagnostics, "load_config", lambda path: cloud_config())
    calls = []

    class OfflineDiagnostic:
        def generate(self, req):
            calls.append(req)
            assert req.provider == Provider.GEMINI and req.model == HYDROGEN
            assert req.parameters.thinking == "low"
            assert (
                req.parameters.max_output_tokens is None
                and req.parameters.timeout_seconds == 20
            )
            return create_gateway().generate(
                GenerationRequest(prompt="Synthetic", synthetic=True)
            )

    def factory(config):
        assert config.max_retries == 0 and not config.fallback_to_groq
        assert config.backup is None
        return OfflineDiagnostic()

    monkeypatch.setattr(diagnostics, "create_gateway", factory)
    assert (
        diagnostics.main(["--live", "--provider", "gemini", "--model", HYDROGEN]) == 0
    )
    assert len(calls) == 1
    output = capsys.readouterr().out
    assert (
        "Synthetic" not in output and "response" not in output and "key" not in output
    )
