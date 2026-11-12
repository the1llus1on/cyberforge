"""Argon2id with library defaults and credential-free errors."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from cyberforge.domain.accounts import ApplicationError


class Passwords:
    def __init__(self) -> None:
        self.hasher = PasswordHasher(type=Type.ID)
        self._dummy = self.hasher.hash("dummy-verification-value")

    def hash(self, password: str) -> str:
        if not 12 <= len(password) <= 1024:
            raise ApplicationError("Пароль має містити від 12 до 1024 символів.")
        return self.hasher.hash(password)

    def verify(self, encoded: str | None, password: str) -> bool:
        if len(password) > 1024:
            return False
        try:
            valid = self.hasher.verify(encoded or self._dummy, password)
            return valid and encoded is not None
        except (VerificationError, InvalidHashError):
            return False
