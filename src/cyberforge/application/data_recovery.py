"""Administrator authorization for private profile backup and recovery."""

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import Role
from cyberforge.persistence.recovery import ProfileRecovery


class DataRecoveryService:
    def __init__(self, accounts: AccountService, storage: ProfileRecovery) -> None:
        self.accounts = accounts
        self.storage = storage
        self._restore: str | None = None

    def _require_admin(self, token: str | None) -> None:
        with self.accounts.transaction() as db:
            self.accounts.require(db, token, Role.ADMINISTRATOR)

    def backup(self, token: str | None) -> str:
        self._require_admin(token)
        return self.storage.backup()

    def backups(self, token: str | None) -> tuple[str, ...]:
        self._require_admin(token)
        return self.storage.available_backups()

    def plan_restore(self, token: str | None, identifier: str) -> None:
        self._require_admin(token)
        self._restore = identifier

    def restore_after_shutdown(self) -> bool:
        identifier, self._restore = self._restore, None
        if identifier is None:
            return False
        self.storage.restore(identifier)
        return True
