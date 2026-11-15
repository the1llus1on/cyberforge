"""Sanitize SDK exceptions without retaining their message, request or response."""

import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import get_args

from cyberforge.llm.contracts import ErrorCategory, GenerationError, ProviderDiagnostics


def provider_diagnostics(error: Exception, status) -> ProviderDiagnostics:
    # Never inspect messages, raw response bodies, failed_generation or traces.
    body = getattr(error, "body", None)
    details = body.get("error", body) if isinstance(body, dict) else {}
    details = details if isinstance(details, dict) else {}
    values = {}
    for field, key in (("error_type", "type"), ("error_code", "code")):
        allowed = get_args(
            get_args(ProviderDiagnostics.model_fields[field].annotation)[0]
        )
        value = details.get(key)
        values[field] = value if isinstance(value, str) and value in allowed else None
    code = values["error_code"]
    kind = "other"
    if code == "context_length_exceeded":
        kind = "context_limit"
    elif code in {
        "max_tokens_exceeded",
        "max_completion_tokens_exceeded",
        "output_limit_exceeded",
    }:
        kind = "output_limit"
    elif code in {
        "json_validate_failed",
        "invalid_json_schema",
        "json_schema_invalid",
        "unsupported_response_format",
    }:
        kind = "structured_output"
    elif status in {400, 404, 413, 422}:
        kind = "invalid_request"
    return ProviderDiagnostics(
        http_status=status if type(status) is int and 100 <= status <= 599 else None,
        kind=kind,
        **values,
    )


def retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0, seconds) if math.isfinite(seconds) else None


def normalize_error(error: Exception) -> GenerationError:
    if isinstance(error, GenerationError):
        return GenerationError(error.category, error.retry_after, error.diagnostics)
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    headers = getattr(getattr(error, "response", None), "headers", {})
    retry_after = retry_after_seconds(headers.get("retry-after"))
    if status in {401, 403}:
        category = ErrorCategory.AUTHORIZATION
    elif status == 429:
        category = ErrorCategory.RATE_LIMIT
    elif status in {500, 502, 503, 504}:
        category = ErrorCategory.UNAVAILABLE
    elif status in {408} or "timeout" in type(error).__name__.lower():
        category = ErrorCategory.TIMEOUT
    elif status is not None:
        category = ErrorCategory.REQUEST
    else:
        category = ErrorCategory.TRANSPORT
    return GenerationError(category, retry_after, provider_diagnostics(error, status))
