"""Sanitize SDK exceptions without retaining their message, request or response."""

import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from cyberforge.llm.contracts import ErrorCategory, GenerationError


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
        return GenerationError(error.category, error.retry_after)
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
    return GenerationError(category, retry_after)
