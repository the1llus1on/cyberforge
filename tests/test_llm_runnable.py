"""Runnable invocation semantics, provider independence and tracing isolation."""

import asyncio
import socket

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableLambda

from cyberforge.llm.config import GatewayConfig
from cyberforge.llm.contracts import (
    Contract,
    ErrorCategory,
    GenerationError,
    GenerationRequest,
    Provider,
)
from cyberforge.llm.factory import configured_request, create_gateway
from cyberforge.llm.gateway import GenerationFailure, LLMGateway
from cyberforge.llm.mock import MockLLMProvider
from cyberforge.llm.runnable import GatewayRunnable


class Message(Contract):
    message: str


def request(**kwargs):
    return GenerationRequest(prompt="Synthetic fixture", synthetic=True, **kwargs)


def test_invoke_structured_output_and_lcel_composition():
    runnable = GatewayRunnable(create_gateway(), Message)
    req = request(operation="structured", schema_version="message-v1")
    result = runnable.invoke(req)
    assert result.structured.message == "Синтетичний приклад"
    assert result.telemetry.local_validation == "passed"
    pipeline = runnable | RunnableLambda(lambda result: result.telemetry.status)
    assert pipeline.invoke(req) == "success"


def test_async_batch_and_whole_response_stream():
    runnable = GatewayRunnable(create_gateway())
    assert len(runnable.batch([request(), request()], {"max_concurrency": 1})) == 2
    assert len(list(runnable.stream(request()))) == 1

    async def exercise():
        assert (await runnable.ainvoke(request())).telemetry.status == "success"
        assert (
            len(await runnable.abatch([request(), request()], {"max_concurrency": 1}))
            == 2
        )
        assert len([item async for item in runnable.astream(request())]) == 1

    asyncio.run(exercise())


def test_no_duplicate_retry_layer_and_normalized_errors():
    provider = MockLLMProvider([GenerationError(ErrorCategory.TIMEOUT)])
    gateway = LLMGateway(GatewayConfig(max_retries=0), {Provider.MOCK: provider})
    with pytest.raises(GenerationFailure) as caught:
        GatewayRunnable(gateway).invoke(request())
    assert caught.value.category == ErrorCategory.TIMEOUT
    assert caught.value.telemetry.retry_count == 0
    assert provider.calls == 1


def test_tracing_and_callback_isolation(monkeypatch):
    class ForbiddenCallback(BaseCallbackHandler):
        def on_chain_start(self, *args, **kwargs):
            pytest.fail("callback received generation input")

    def forbidden(*args, **kwargs):
        pytest.fail("tracing attempted network access")

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "synthetic-tracing-key")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = GatewayRunnable(create_gateway()).invoke(
        request(),
        {"callbacks": [ForbiddenCallback()], "metadata": {"private": "ignored"}},
    )
    assert result.telemetry.status == "success"


def test_langchain_serialization_excludes_sensitive_content():
    from langchain_core.load.dump import dumpd

    req = GenerationRequest(prompt="private-prompt", synthetic=True)
    result = GatewayRunnable(create_gateway()).invoke(req)
    assert "private-prompt" not in str(dumpd(req))
    assert result.text not in str(dumpd(result))


def test_factory_uses_config_and_is_offline_without_keys(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config = GatewayConfig()
    req = configured_request(config, prompt="Synthetic", synthetic=True)
    assert create_gateway(config).generate(req).telemetry.provider == Provider.MOCK
