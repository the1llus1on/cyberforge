"""Single retry/fallback/validation boundary for future orchestrators."""

import random
import time
from collections.abc import Callable, Mapping
from typing import Protocol

from pydantic import BaseModel, PydanticInvalidForJsonSchema, ValidationError

from cyberforge.llm.config import (
    APPROVED_MODELS,
    THINKING_LEVELS,
    GatewayConfig,
    validate_selection,
)
from cyberforge.llm.contracts import (
    ErrorCategory,
    GenerationError,
    GenerationRequest,
    GenerationResult,
    GenerationTelemetry,
    Provider,
    ProviderResponse,
    Usage,
)
from cyberforge.llm.limits import RateLimiter
from cyberforge.llm.schemas import groq_output_schema

RETRYABLE = {ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE, ErrorCategory.RATE_LIMIT}
FALLBACK_ALLOWED = {ErrorCategory.TIMEOUT, ErrorCategory.UNAVAILABLE}


class LLMProvider(Protocol):
    def generate(
        self, request: GenerationRequest, schema: dict | None
    ) -> ProviderResponse: ...


class TelemetrySink(Protocol):
    """Optional metadata-only sink; persistence is deferred."""

    def record(self, telemetry: GenerationTelemetry) -> None: ...


class GenerationFailure(GenerationError):
    def __init__(
        self,
        category: ErrorCategory,
        telemetry: GenerationTelemetry,
        retry_after: float | None = None,
    ):
        super().__init__(category, retry_after)
        self.telemetry = telemetry


class LLMGateway:
    def __init__(
        self,
        config: GatewayConfig,
        providers: Mapping[Provider, LLMProvider],
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        sink: TelemetrySink | None = None,
    ) -> None:
        self.config = config
        self._providers = dict(providers)
        self._clock, self._sleep, self._jitter = clock, sleep, jitter
        self._limiter = RateLimiter(config.limits, clock)
        self._sink = sink

    def _backup_for(self, request: GenerationRequest) -> tuple[Provider, str] | None:
        if request.provider == Provider.MOCK:
            return None
        backup = self.config.backup
        if backup is not None:
            if (
                backup.enabled
                and backup.access_verified
                and (request.provider, request.model)
                == (self.config.provider, self.config.model)
            ):
                return backup.provider, backup.model
            return None
        # Deprecated compatibility path, using the same one-hop execution loop.
        if self.config.fallback_to_groq and request.provider == Provider.GEMINI:
            return Provider.GROQ, "openai/gpt-oss-120b"
        return None

    def generate(
        self, request: GenerationRequest, output_type: type[BaseModel] | None = None
    ) -> GenerationResult:
        started = self._clock()
        active = request
        retries = 0
        fallback = False
        response = None
        validation = None
        error = None
        retry_after = None
        structured = None
        schema_projection = None
        try:
            if (request.operation == "structured") != (output_type is not None):
                raise GenerationError(ErrorCategory.CONFIGURATION)
            if output_type is not None and request.schema_version is None:
                raise GenerationError(ErrorCategory.CONFIGURATION)
            while True:
                validate_selection(
                    active.provider, active.model, active.parameters.thinking
                )
                if (
                    active.model == "gemini-4-hydrogen"
                    and active.parameters.temperature is not None
                ):
                    active = active.model_copy(
                        update={
                            "parameters": active.parameters.model_copy(
                                update={"temperature": None}
                            )
                        }
                    )
                schema_projection = None
                try:
                    schema = output_type.model_json_schema() if output_type else None
                except PydanticInvalidForJsonSchema:
                    raise GenerationError(ErrorCategory.SCHEMA) from None
                if schema is not None and active.provider == Provider.GROQ:
                    schema, schema_projection = groq_output_schema(output_type, schema)
                provider = self._providers.get(active.provider)
                if provider is None:
                    raise GenerationError(ErrorCategory.CONFIGURATION)
                attempt = 0
                try:
                    while True:
                        self._limiter.reserve(active, schema)
                        try:
                            if attempt:
                                retries += 1
                            response = provider.generate(active, schema)
                            break
                        except GenerationError as exc:
                            delay = min(
                                self.config.max_backoff_seconds,
                                2**attempt + self._jitter(),
                            )
                            if exc.category == ErrorCategory.RATE_LIMIT:
                                self._limiter.defer(
                                    active.provider.value,
                                    exc.retry_after
                                    if exc.retry_after is not None
                                    else delay,
                                )
                            if (
                                exc.category not in RETRYABLE
                                or attempt >= self.config.max_retries
                            ):
                                raise
                            if exc.retry_after is not None:
                                if exc.retry_after > self.config.max_backoff_seconds:
                                    raise
                                delay = max(delay, exc.retry_after)
                            self._sleep(delay)
                            attempt += 1
                    break
                except GenerationError as exc:
                    target = self._backup_for(request)
                    if (
                        not fallback
                        and target is not None
                        and exc.category in FALLBACK_ALLOWED
                    ):
                        target_provider, target_model = target
                        validate_selection(target_provider, target_model, None)
                        parameters = request.parameters
                        thinking = parameters.thinking
                        if (
                            thinking is not None
                            and thinking not in THINKING_LEVELS[target_model]
                        ):
                            # Fixed compatibility mappings; no AUTO routing.
                            mapped = {"minimal": "low", "xhigh": "high"}.get(thinking)
                            if mapped is None:
                                raise GenerationError(
                                    ErrorCategory.CONFIGURATION
                                ) from None
                            parameters = parameters.model_copy(
                                update={"thinking": mapped}
                            )
                        active = active.model_copy(
                            update={
                                "provider": target_provider,
                                "model": target_model,
                                "parameters": parameters,
                            }
                        )
                        fallback = True
                    else:
                        raise
            if output_type is not None:
                try:
                    structured = output_type.model_validate_json(
                        response.text, strict=True
                    )
                    validation = "passed"
                except ValidationError:
                    validation = "failed"
                    raise GenerationError(ErrorCategory.VALIDATION) from None
        except GenerationError as exc:
            error = exc.category
            retry_after = exc.retry_after
        except Exception:
            # Unexpected transport/schema implementation details are never exported.
            error = ErrorCategory.TRANSPORT
        telemetry = GenerationTelemetry(
            provider=active.provider,
            requested_provider=request.provider,
            requested_model=request.model
            if request.model in APPROVED_MODELS[request.provider]
            else "<invalid-model>",
            effective_model=active.model
            if active.model in APPROVED_MODELS[active.provider]
            else "<invalid-model>",
            actual_model=response.actual_model if response else None,
            operation=request.operation,
            prompt_version=request.prompt_version,
            schema_version=request.schema_version,
            requested_parameters=request.parameters,
            effective_parameters=active.parameters,
            schema_projection=schema_projection,
            elapsed_seconds=max(0, self._clock() - started),
            usage=response.usage if response else Usage(),
            status="error" if error else "success",
            retry_count=retries,
            fallback=fallback,
            error=error,
            local_validation=validation,
        )
        if self._sink is not None:
            try:
                self._sink.record(telemetry)
            except Exception:
                # Best-effort observability must not leak sink errors or cause
                # callers to repeat an otherwise completed cloud generation.
                pass
        if error is not None:
            raise GenerationFailure(error, telemetry, retry_after) from None
        return GenerationResult(
            text=response.text, structured=structured, telemetry=telemetry
        )
