"""Optional LangChain composition over the existing execution boundary."""

from typing import Any

from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel

from cyberforge.llm.contracts import GenerationRequest, GenerationResult
from cyberforge.llm.gateway import LLMGateway


class GatewayRunnable(Runnable[GenerationRequest, GenerationResult]):
    """invoke/ainvoke/batch/stream share the gateway's retry and quota policy.

    This boundary deliberately emits no LangChain callbacks. Only the gateway's
    metadata-only TelemetrySink is supported for generation observability.
    """

    def __init__(
        self, gateway: LLMGateway, output_type: type[BaseModel] | None = None
    ) -> None:
        self._gateway = gateway
        self._output_type = output_type

    def invoke(
        self,
        input: GenerationRequest,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        # No _call_with_config/RunnableLambda: these trace raw inputs/outputs.
        # Ignore caller tracing metadata/callbacks; never attach credentials.
        from langsmith import tracing_context

        with tracing_context(enabled=False):
            return self._gateway.generate(input, self._output_type)
