"""Stateless Gemini Interactions adapter; no legacy generateContent path."""

import warnings

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


class GeminiProvider:
    def __init__(self, api_key: SecretStr | None, *, client_factory=None) -> None:
        self._key = api_key
        self._client_factory = client_factory

    @private_sdk_logs()
    def generate(
        self, request: GenerationRequest, schema: dict | None
    ) -> ProviderResponse:
        validate_selection(Provider.GEMINI, request.model, request.parameters.thinking)
        if not self._key or not self._key.get_secret_value().strip():
            raise GenerationError(ErrorCategory.MISSING_CREDENTIALS)
        params = request.parameters
        generation_config = {
            "max_output_tokens": params.max_output_tokens,
            "thinking_summaries": "none",
        }
        if request.model != "gemini-4-hydrogen" and params.temperature is not None:
            generation_config["temperature"] = params.temperature
        if params.thinking is not None:
            generation_config["thinking_level"] = params.thinking
        kwargs = {
            "model": request.model,
            "input": request.prompt,
            "store": False,
            "background": False,
            "stream": False,
            "automatic_continuation": False,
            "timeout": params.timeout_seconds,
            "generation_config": generation_config,
        }
        if schema is not None:
            kwargs["response_format"] = {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            }
        failure = None
        result = None
        try:
            from google import genai
            from google.genai import types

            factory = self._client_factory or genai.Client
            with factory(
                api_key=self._key.get_secret_value(),
                vertexai=False,
                http_options=types.HttpOptions(
                    base_url="https://generativelanguage.googleapis.com",
                    api_version="v1",
                    timeout=int(params.timeout_seconds * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            ) as client:
                # google-genai 2.34 converts attempts=0 to 1 on the parent
                # client, then Interactions interprets it as a retry count.
                # Disable the generated resource's retry strategy explicitly.
                # This SDK compatibility point is pinned and transport-tested.
                retry_config = getattr(
                    getattr(client.interactions, "sdk_configuration", None),
                    "retry_config",
                    None,
                )
                if retry_config is None or not hasattr(retry_config, "strategy"):
                    raise GenerationError(ErrorCategory.CONFIGURATION)
                retry_config.strategy = "none"
                with warnings.catch_warnings():
                    # We deliberately reject incomplete output below rather
                    # than let the SDK suggest paid continuation in diagnostics.
                    warnings.filterwarnings(
                        "ignore",
                        message="Interaction stopped before completion.*",
                        category=UserWarning,
                    )
                    result = client.interactions.create(**kwargs)
        except Exception as exc:
            failure = normalize_error(exc)
        if failure is not None:
            raise failure from None
        # Only final model output is returned. Never expose thoughts/signatures,
        # raw diagnostic messages, tool calls or continuation tokens.
        for step in result.steps or []:
            status = getattr(step, "error", None)
            if status is not None:
                reasons = {
                    str(detail.get("reason", "")).lower()
                    for detail in status.details or []
                }
                if reasons & {
                    "safety",
                    "content_filter",
                    "blocked",
                    "prohibited_content",
                }:
                    raise GenerationError(ErrorCategory.SAFETY)
                category = {
                    4: ErrorCategory.TIMEOUT,
                    7: ErrorCategory.AUTHORIZATION,
                    8: ErrorCategory.RATE_LIMIT,
                    14: ErrorCategory.UNAVAILABLE,
                }.get(status.code, ErrorCategory.REQUEST)
                raise GenerationError(category)
        for error in result.errors or []:
            code = (error.code or "").lower().rsplit("/", 1)[-1]
            if code in {"safety", "content_filter", "blocked", "prohibited_content"}:
                raise GenerationError(ErrorCategory.SAFETY)
            raise GenerationError(ErrorCategory.REQUEST)
        if result.status == "budget_exceeded":
            raise GenerationError(ErrorCategory.BUDGET)
        if result.status != "completed" or not result.output_text:
            raise GenerationError(ErrorCategory.VALIDATION)
        usage = result.usage
        return ProviderResponse(
            text=result.output_text,
            actual_model=result.model,
            usage=Usage(
                input_tokens=usage.total_input_tokens if usage else None,
                output_tokens=usage.total_output_tokens if usage else None,
                reasoning_tokens=usage.total_thought_tokens if usage else None,
            ),
        )
