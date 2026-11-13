"""One contract and local structured validator across every provider adapter."""

import httpx
import pytest
from google import genai
from groq import Groq
from pydantic import SecretStr

from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import (
    Contract,
    GenerationRequest,
    Provider,
    ProviderResponse,
)
from cyberforge.llm.gateway import GenerationFailure, LLMGateway
from cyberforge.llm.gemini_provider import GeminiProvider
from cyberforge.llm.groq_provider import GroqProvider
from cyberforge.llm.mock import MockLLMProvider
from cyberforge.llm.runnable import GatewayRunnable


class Message(Contract):
    message: str


@pytest.mark.parametrize(
    "provider,model",
    [
        (Provider.GEMINI, "gemini-3.8-flash"),
        (Provider.GROQ, "openai/gpt-oss-120b"),
        (Provider.MOCK, "mock-v1"),
    ],
)
@pytest.mark.parametrize(
    "text,valid", [('{"message":"fixture"}', True), ('{"message":1}', False)]
)
def test_shared_runnable_contract(provider, model, text, valid):
    def handler(req):
        if provider == Provider.GEMINI:
            payload = {
                "status": "completed",
                "model": model,
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": text}],
                    }
                ],
            }
        else:
            payload = {
                "id": "fixture",
                "created": 0,
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": text},
                    }
                ],
            }
        return httpx.Response(200, json=payload)

    def google_factory(**kwargs):
        kwargs["http_options"] = kwargs["http_options"].model_copy(
            update={
                "httpx_client": httpx.Client(transport=httpx.MockTransport(handler)),
            }
        )
        return genai.Client(**kwargs)

    def groq_factory(**kwargs):
        return Groq(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler))
        )

    key = SecretStr("synthetic-test-key")
    adapters = {
        Provider.GEMINI: GeminiProvider(key, client_factory=google_factory),
        Provider.GROQ: GroqProvider(key, client_factory=groq_factory),
        Provider.MOCK: MockLLMProvider(
            [ProviderResponse(text=text, actual_model=model)]
        ),
    }
    runnable = GatewayRunnable(LLMGateway(GatewayConfig(), adapters), Message)
    request = GenerationRequest(
        prompt="Synthetic",
        synthetic=True,
        provider=provider,
        model=model,
        operation="structured",
        schema_version="message-v1",
    )
    if valid:
        result = runnable.invoke(request)
        assert result.structured.message == "fixture"
        assert result.telemetry.provider == provider
        assert result.telemetry.local_validation == "passed"
    else:
        with pytest.raises(GenerationFailure, match="validation") as caught:
            runnable.invoke(request)
        assert caught.value.telemetry.local_validation == "failed"
