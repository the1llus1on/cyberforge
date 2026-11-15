"""Groq adapter. SDK types remain entirely inside this module."""

from pydantic import SecretStr

from cyberforge.llm.config import validate_selection
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    GenerationRequest,
    Provider,
    ProviderResponse,
    Usage,
)
from cyberforge.llm.privacy import private_sdk_logs
from cyberforge.llm.provider_errors import normalize_error
from cyberforge.llm.schemas import groq_strict_schema


class GroqProvider:
    def __init__(self, api_key: SecretStr | None, *, client_factory=None) -> None:
        self._key = api_key
        self._client_factory = client_factory

    @private_sdk_logs()
    def generate(
        self, request: GenerationRequest, schema: dict | None
    ) -> ProviderResponse:
        validate_selection(Provider.GROQ, request.model, request.parameters.thinking)
        if not self._key or not self._key.get_secret_value().strip():
            raise GenerationError(ErrorCategory.MISSING_CREDENTIALS)
        response_format = None
        if schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "cyberforge_artifact",
                    "strict": True,
                    "schema": groq_strict_schema(schema),
                },
            }
        params = request.parameters
        kwargs = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if params.max_output_tokens is not None:
            kwargs["max_completion_tokens"] = params.max_output_tokens
        if params.temperature is not None:
            kwargs["temperature"] = params.temperature
        if response_format is not None:
            kwargs["response_format"] = response_format
        if params.thinking is not None:
            kwargs["reasoning_effort"] = params.thinking
        failure = None
        result = None
        try:
            from groq import Groq

            factory = self._client_factory or Groq
            with factory(
                api_key=self._key.get_secret_value(),
                timeout=params.timeout_seconds,
                max_retries=0,
                base_url="https://api.groq.com",
            ) as client:
                result = client.chat.completions.create(**kwargs)
        except Exception as exc:
            failure = normalize_error(exc)
        if failure is not None:
            raise failure from None
        choice = result.choices[0] if result.choices else None
        if choice is None:
            raise GenerationError(ErrorCategory.VALIDATION)
        if (
            getattr(choice.message, "refusal", None)
            or choice.finish_reason == "content_filter"
        ):
            raise GenerationError(ErrorCategory.SAFETY)
        if choice.finish_reason != "stop" or not choice.message.content:
            raise GenerationError(ErrorCategory.VALIDATION)
        usage = result.usage
        return ProviderResponse(
            text=choice.message.content,
            actual_model=result.model,
            usage=Usage(
                input_tokens=usage.prompt_tokens if usage else None,
                output_tokens=usage.completion_tokens if usage else None,
                reasoning_tokens=getattr(
                    getattr(usage, "completion_tokens_details", None),
                    "reasoning_tokens",
                    None,
                ),
            ),
        )
