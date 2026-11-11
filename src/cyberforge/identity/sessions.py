"""Opaque process-local sessions. Never persist or log session tokens."""

from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe


@dataclass(frozen=True, repr=False)
class SessionRecord:
    user_id: int
    auth_version: int
    credential_tag: str


class Sessions:
    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}

    def issue(self, user_id: int, auth_version: int, password_hash: str) -> str:
        token = token_urlsafe(32)
        self._records[token] = SessionRecord(
            user_id, auth_version, sha256(password_hash.encode()).hexdigest()
        )
        return token

    def get(self, token: str | None) -> SessionRecord | None:
        return self._records.get(token or "")

    def revoke(self, token: str | None) -> None:
        self._records.pop(token or "", None)

    def clear(self) -> None:
        self._records.clear()
