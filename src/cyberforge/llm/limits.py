"""Conservative rolling budgets shared by requests on one gateway instance."""

import json
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock
from time import monotonic

from cyberforge.llm.config import RateLimits
from cyberforge.llm.contracts import ErrorCategory, GenerationError, GenerationRequest


class RateLimiter:
    def __init__(
        self, limits: dict[str, RateLimits], clock: Callable[[], float] = monotonic
    ) -> None:
        self._limits = limits
        self._clock = clock
        self._entries: dict[str, deque[tuple[float, int]]] = defaultdict(deque)
        self._cooldowns: dict[str, float] = {}
        self._lock = Lock()

    def defer(self, provider: str, seconds: float) -> None:
        with self._lock:
            self._cooldowns[provider] = max(
                self._cooldowns.get(provider, 0), self._clock() + seconds
            )

    def reserve(self, request: GenerationRequest, schema: dict | None = None) -> None:
        # Byte count is an intentionally conservative input-token upper estimate.
        # Add output (including thinking) only when explicitly bounded. Unknown
        # provider-default output cannot be reserved; this is not a billing cap.
        # Failures keep their reservation for explicitly configured quotas.
        tokens = len(request.prompt.encode("utf-8")) + (
            request.parameters.max_output_tokens or 0
        )
        if schema is not None:
            tokens += len(json.dumps(schema, ensure_ascii=False).encode("utf-8"))
        keys = [request.provider.value, f"{request.provider.value}:{request.model}"]
        with self._lock:
            now = self._clock()
            remaining = self._cooldowns.get(request.provider.value, 0) - now
            if remaining > 0:
                raise GenerationError(ErrorCategory.RATE_LIMIT, remaining)
            for key in keys:
                limit = self._limits.get(key)
                if limit is None:
                    continue
                entries = self._entries[key]
                while entries and entries[0][0] <= now - 86400:
                    entries.popleft()
                minute = [(t, n) for t, n in entries if t > now - 60]
                if (
                    (limit.rpd is not None and len(entries) >= limit.rpd)
                    or (limit.rpm is not None and len(minute) >= limit.rpm)
                    or (
                        limit.tpd is not None
                        and sum(n for _, n in entries) + tokens > limit.tpd
                    )
                    or (
                        limit.tpm is not None
                        and sum(n for _, n in minute) + tokens > limit.tpm
                    )
                ):
                    raise GenerationError(ErrorCategory.BUDGET)
            for key in keys:
                if key not in self._limits:
                    continue
                self._entries[key].append((now, tokens))
