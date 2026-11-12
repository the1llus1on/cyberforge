"""CLI opt-in guard; enabled-path tests inject an offline gateway."""

import pytest

from cyberforge.llm import diagnostics
from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    GenerationRequest,
    Provider,
)
from cyberforge.llm.factory import create_gateway
from cyberforge.llm.gateway import LLMGateway
from cyberforge.llm.mock import MockLLMProvider


@pytest.mark.parametrize(
    "args",
    [
        ["--provider", "gemini", "--model", "gemini-3.8-flash"],
        ["--live", "--provider", "gemini", "--model", "unapproved"],
    ],
)
def test_disabled_or_unapproved_never_reads_config_or_creates_client(monkeypatch, args):
    def forbidden(*args, **kwargs):
        pytest.fail("diagnostic guard bypassed")

    monkeypatch.setattr(diagnostics, "load_config", forbidden)
    monkeypatch.setattr(diagnostics, "create_gateway", forbidden)
    with pytest.raises(SystemExit) as caught:
        diagnostics.main(args)
    assert caught.value.code == 2


@pytest.mark.parametrize(
    "provider,model",
    [
        ("gemini", "gemini-3.8-flash"),
        ("gemini", "gemini-3.5-flash-lite"),
        ("groq", "openai/gpt-oss-120b"),
    ],
)
def test_one_bounded_attempt_and_no_fallback(monkeypatch, capsys, provider, model):
    calls = []

    class OfflineDiagnostic:
        def generate(self, request):
            calls.append(request)
            return create_gateway().generate(
                GenerationRequest(
                    prompt="Synthetic",
                    synthetic=True,
                )
            )

    def factory(config):
        assert config.max_retries == 0
        assert config.fallback_to_groq is False
        return OfflineDiagnostic()

    monkeypatch.setattr(diagnostics, "load_config", lambda path: GatewayConfig())
    monkeypatch.setattr(diagnostics, "create_gateway", factory)
    assert diagnostics.main(["--live", "--provider", provider, "--model", model]) == 0
    assert len(calls) == 1
    assert calls[0].parameters.max_output_tokens == 256
    assert calls[0].parameters.timeout_seconds == 20
    output = capsys.readouterr().out
    assert "prompt" not in output
    assert "Synthetic" not in output
    assert '"outcome": "success"' in output


def test_diagnostic_reports_only_safe_error(monkeypatch, capsys):
    mock = MockLLMProvider([GenerationError(ErrorCategory.AUTHORIZATION)])
    monkeypatch.setattr(diagnostics, "load_config", lambda path: GatewayConfig())
    monkeypatch.setattr(
        diagnostics,
        "create_gateway",
        lambda config: LLMGateway(
            config,
            {Provider.GROQ: mock},
        ),
    )
    assert (
        diagnostics.main(
            ["--live", "--provider", "groq", "--model", "openai/gpt-oss-120b"]
        )
        == 1
    )
    assert '"outcome": "authorization"' in capsys.readouterr().out
