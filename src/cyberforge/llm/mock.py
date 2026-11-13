"""Deterministic scripted provider. No SDK imports and no network access."""

from collections import deque

from cyberforge.llm.contracts import (
    GenerationError,
    GenerationRequest,
    ProviderResponse,
    Usage,
)


class MockLLMProvider:
    def __init__(
        self,
        responses: list[ProviderResponse | GenerationError] | None = None,
    ) -> None:
        self._responses = deque(responses or [])
        self.calls = 0

    def generate(
        self, request: GenerationRequest, schema: dict | None
    ) -> ProviderResponse:
        self.calls += 1
        if self._responses:
            response = self._responses.popleft()
            if isinstance(response, GenerationError):
                raise response
            return response
        return ProviderResponse(
            text='{"message":"Синтетичний приклад"}'
            if schema is not None
            else "Синтетичний приклад",
            actual_model="mock-v1",
            usage=Usage(input_tokens=8, output_tokens=8),
        )
