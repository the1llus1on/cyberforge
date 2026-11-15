"""Live acceptance runner is exercised only with a scripted provider."""

import json

import pytest

from cyberforge.agents.contracts import EmailInputV1
from cyberforge.agents.email_live_check import main, run_check
from cyberforge.application.email_demo import demo_gateway
from cyberforge.llm.config import GatewayConfig, RateLimits
from cyberforge.llm.contracts import ErrorCategory, GenerationError, Provider
from cyberforge.llm.gateway import LLMGateway


class Scripted:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def generate(self, request, schema):
        self.calls.append((request, schema))
        if self.fail:
            raise GenerationError(ErrorCategory.TIMEOUT)
        data = json.loads(
            request.prompt.split("BEGIN_UNTRUSTED_JSON\n")[1].split(
                "\nEND_UNTRUSTED_JSON"
            )[0]
        )
        data.pop("context_token")
        previous = data.pop("previous", None)
        if previous:
            # Reconstruct the valid previous envelope from the first response.
            data["previous"] = self.first
        source = EmailInputV1.model_validate_json(json.dumps(data))
        gateway = demo_gateway(source)
        response = gateway._providers[Provider.MOCK]._responses[0]
        if previous is None:
            from cyberforge.agents.specialized import EmailScenarioAgent

            self.first = (
                EmailScenarioAgent(gateway).run(source).draft.model_dump(mode="json")
            )
        return response


def gateway(provider):
    return LLMGateway(
        GatewayConfig(
            provider=Provider.GROQ,
            model="openai/gpt-oss-120b",
            max_retries=0,
            limits={
                k: RateLimits(tpm=128000, tpd=128000)
                for k in ("groq", "groq:openai/gpt-oss-120b")
            },
        ),
        {Provider.GROQ: provider},
    )


def test_no_live_opt_in_never_constructs_gateway(monkeypatch):
    from cyberforge.agents import email_live_check

    monkeypatch.setattr(
        email_live_check, "create_gateway", lambda *a: pytest.fail("Network")
    )
    with pytest.raises(SystemExit):
        main([])


def test_two_requests_and_metadata_only(capsys):
    provider = Scripted()
    assert run_check(gateway(provider))
    assert len(provider.calls) == 2
    for request, schema in provider.calls:
        assert schema["additionalProperties"] is False
        assert request.parameters.max_output_tokens == 4096
        assert request.prompt_version == "email-prompt-v3"
    output = capsys.readouterr().out
    assert "body_text" not in output and "context_token" not in output
    assert 'protected_fields_preserved": true' in output


def test_first_failure_stops_without_retry(capsys):
    provider = Scripted(fail=True)
    assert not run_check(gateway(provider))
    assert len(provider.calls) == 1
    assert "timeout" in capsys.readouterr().out


@pytest.mark.parametrize(
    "shared,email,expected",
    [
        (None, None, 4096),
        (None, 8192, 8192),
        (50000, None, 50000),
        (50000, 60000, 60000),
    ],
)
def test_email_optional_limit_inherits_or_overrides(shared, email, expected):
    from cyberforge.llm.contracts import GenerationParameters

    provider = Scripted()
    config = GatewayConfig(
        provider=Provider.GROQ,
        model="openai/gpt-oss-120b",
        max_retries=0,
        parameters=GenerationParameters(max_output_tokens=shared),
        email_max_output_tokens=email,
    )
    assert run_check(LLMGateway(config, {Provider.GROQ: provider}))
    assert all(
        req.parameters.max_output_tokens == expected for req, _ in provider.calls
    )


@pytest.mark.parametrize(
    "limit,env_limit,expected",
    [
        (None, None, 4096),
        (8192, None, 8192),
        (50000, None, 50000),
        (None, "16000", 16000),
        (8192, "16000", 8192),
    ],
)
def test_owner_cli_email_default_and_overrides(monkeypatch, limit, env_limit, expected):
    from cyberforge.agents import email_live_check

    monkeypatch.setattr(email_live_check, "dotenv_values", lambda *a, **kw: {})
    monkeypatch.setenv("GROQ_API_KEY", "fixture-key")
    monkeypatch.delenv("CYBERFORGE_EMAIL_MAX_OUTPUT_TOKENS", raising=False)
    if env_limit is not None:
        monkeypatch.setenv("CYBERFORGE_EMAIL_MAX_OUTPUT_TOKENS", env_limit)
    configs = []
    provider = Scripted()

    def factory(config):
        configs.append(config)
        return LLMGateway(config, {Provider.GROQ: provider})

    monkeypatch.setattr(email_live_check, "create_gateway", factory)
    assert (
        main(["--live", *(["--max-output-tokens", str(limit)] if limit else [])]) == 0
    )
    assert len(provider.calls) == 2
    assert all(
        req.parameters.max_output_tokens == expected for req, _ in provider.calls
    )
    assert configs[0].limits == {} and configs[0].max_retries == 0
    assert configs[0].backup is None


def test_gemini_email_keeps_unset_output_limit():
    provider = Scripted()
    config = GatewayConfig(
        provider=Provider.GEMINI, model="gemini-4-hydrogen", max_retries=0
    )
    assert run_check(LLMGateway(config, {Provider.GEMINI: provider}))
    assert len(provider.calls) == 2
    assert all(req.parameters.max_output_tokens is None for req, _ in provider.calls)


def test_email_prompt_v3_uses_context_and_keeps_untyped_parameters_local():
    from cyberforge.agents.email_live_check import acceptance_source
    from cyberforge.agents.prompts import build_prompt, task_data
    from cyberforge.agents.specialized import EmailScenarioAgent
    from cyberforge.llm.config import load_config

    source = acceptance_source()
    data = task_data(source)
    assert data["parameters"]["nist_cues"]
    for field in (
        "topic",
        "difficulty",
        "audience",
        "description",
        "learning_objective",
        "tactics",
    ):
        assert data["parameters"][field]
    assert "generation_parameters" not in data["parameters"]
    prompt = build_prompt(
        "email", source, EmailScenarioAgent.context_token(source), False
    )
    assert "EMAIL-PROMPT-V3" in prompt and "BEGIN_UNTRUSTED_JSON" in prompt
    assert "Ordinary" in prompt and "fictional identities" in prompt
    assert "Use reserved .invalid addresses only" not in prompt
    assert "NIST" in prompt and "never verified" in prompt
    assert "main_body" in prompt and "previous" in prompt
    assert GatewayConfig().parameters.max_output_tokens is None
    assert GatewayConfig().email_max_output_tokens is None
    assert (
        load_config(
            environ={"CYBERFORGE_EMAIL_MAX_OUTPUT_TOKENS": "2048"},
            env_file=__import__("pathlib").Path("/tmp/no-cyberforge-env"),
        ).email_max_output_tokens
        == 2048
    )
