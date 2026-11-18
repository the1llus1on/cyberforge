"""Opaque process-local sessions. Never persist or log session tokens."""

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe
from threading import RLock


@dataclass(frozen=True, repr=False)
class SessionRecord:
    user_id: int
    auth_version: int
    credential_tag: str


class Sessions:
    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = RLock()

    def issue(self, user_id: int, auth_version: int, password_hash: str) -> str:
        token = token_urlsafe(32)
        record = SessionRecord(
            user_id, auth_version, sha256(password_hash.encode()).hexdigest()
        )
        with self._lock:
            self._records[token] = record
        return token

    def get(self, token: str | None) -> SessionRecord | None:
        with self._lock:
            return self._records.get(token or "")

    def revoke(self, token: str | None) -> None:
        with self._lock:
            self._records.pop(token or "", None)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    @contextmanager
    def guard(self, token: str | None):
        """Serialize revocation with a short, already-authorized local publication."""
        with self._lock:
            yield self.get(token)
