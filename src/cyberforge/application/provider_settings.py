"""Session-authorized provider credentials and atomically replaced public settings."""

import hashlib
import os
import re
from collections.abc import Callable
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.llm.config import GatewayConfig, validate_selection
from cyberforge.llm.contracts import (
    GenerationError,
    GenerationParameters,
    GenerationRequest,
    Provider,
)
from cyberforge.llm.factory import create_gateway
from cyberforge.llm.secret_store import CloudProvider, SecretStore, SecretStoreError
from cyberforge.persistence.profile import PrivateProfile

_UNAVAILABLE = "Налаштування або сховище ключів недоступні."
_NO_KEY = "Спочатку збережіть ключ для цього провайдера."


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    profile_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    revisions: dict[CloudProvider, str] = Field(default_factory=dict)
    provider: CloudProvider | None = None
    model: str | None = None


class ProviderSettings:
    def __init__(
        self,
        accounts: AccountService,
        profile: PrivateProfile,
        store: Callable[[str], SecretStore],
    ) -> None:
        self.accounts, self.profile = accounts, profile
        self.path = profile.root / "providers.json"
        self._store_factory = store
        self.guard = RLock()

    def _require(self, token: str | None, *roles: Role) -> None:
        with self.accounts.transaction() as db:
            self.accounts.require(db, token, *roles)

    def _load(self, *, initialize: bool = False) -> _Settings | None:
        try:
            self.profile.validate(self.path, missing=True)
            if not self.path.exists():
                if not initialize:
                    return None
                state = _Settings(profile_id=uuid4().hex)
                self._save(state)
                return state
            with self.path.open("rb") as stream:
                return _Settings.model_validate_json(stream.read(8193))
        except (OSError, ValueError):
            raise ApplicationError(_UNAVAILABLE) from None

    def _save(self, state: _Settings) -> None:
        stage = self.profile.root / ("provider-" + uuid4().hex + ".json")
        try:
            self.profile.validate(self.path, missing=True)
            fd = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(state.model_dump_json().encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            self.profile.validate(stage)
            stage.replace(self.path)
        except OSError:
            raise ApplicationError(_UNAVAILABLE) from None
        finally:
            stage.unlink(missing_ok=True)

    def _key(self, state: _Settings, provider: CloudProvider) -> SecretStr | None:
        if provider not in state.revisions:
            return None
        try:
            return self._store_factory(state.profile_id).read(provider)
        except (SecretStoreError, OSError):
            raise ApplicationError(_UNAVAILABLE) from None

    @staticmethod
    def _validate(provider: CloudProvider, model: str) -> None:
        try:
            validate_selection(Provider(provider), model, None)
            if provider not in {"groq", "gemini"}:
                raise ValueError
        except (GenerationError, ValueError):
            raise ApplicationError("Непідтримувані провайдер або модель.") from None

    def status(self, token: str | None):
        with self.guard:
            self._require(token, Role.ADMINISTRATOR)
            state = self._load(initialize=True)
            return (
                state.profile_id,
                state.provider,
                state.model,
                tuple(
                    provider
                    for provider in state.revisions
                    if self._key(state, provider)
                ),
            )

    def replace_key(
        self, token: str | None, provider: CloudProvider, value: SecretStr | None
    ) -> None:
        if provider not in {"groq", "gemini"}:
            raise ApplicationError("Непідтримуваний провайдер.")
        if value is not None and not re.fullmatch(
            r"[!-~]{1,512}", value.get_secret_value()
        ):
            raise ApplicationError("Введіть дійсний ключ API.")
        with self.guard:
            self._require(token, Role.ADMINISTRATOR)
            state = self._load(initialize=True)
            revisions = dict(state.revisions)
            revisions.pop(provider, None)
            disabled = state.model_copy(
                update={
                    "revisions": revisions,
                    "provider": None if state.provider == provider else state.provider,
                    "model": None if state.provider == provider else state.model,
                }
            )
            self._save(disabled)
            try:
                store = self._store_factory(state.profile_id)
                if value is None:
                    store.delete(provider)
                else:
                    store.write(provider, value)
                    self._save(
                        disabled.model_copy(
                            update={"revisions": revisions | {provider: uuid4().hex}}
                        )
                    )
            except (SecretStoreError, OSError):
                raise ApplicationError(_UNAVAILABLE) from None

    def activate(
        self, token: str | None, provider: CloudProvider | None, model: str | None
    ) -> None:
        with self.guard:
            self._require(token, Role.ADMINISTRATOR)
            state = self._load(initialize=True)
            if provider is not None:
                self._validate(provider, model or "")
                if self._key(state, provider) is None:
                    raise ApplicationError(_NO_KEY)
            self._save(
                state.model_copy(
                    update={"provider": provider, "model": model if provider else None}
                )
            )

    def _active_key(self, token: str | None, *roles: Role):
        self._require(token, *roles)
        state = self._load()
        if state is None or state.provider is None or state.model is None:
            return None
        self._validate(state.provider, state.model)
        key = self._key(state, state.provider)
        if key is None:
            raise ApplicationError(_NO_KEY)
        stamp = hashlib.sha256(
            (state.revisions[state.provider] + "\0" + key.get_secret_value()).encode()
        ).hexdigest()
        return state.profile_id, state.provider, state.model, stamp, key

    def advisory_key(self, token: str | None):
        with self.guard:
            return self._active_key(token, Role.INSTRUCTOR)

    def active_revision(self, token: str | None) -> str | None:
        with self.guard:
            route = self._active_key(token, Role.ADMINISTRATOR)
            return route[3] if route else None

    def active_route(self) -> tuple[Provider, str]:
        with self.guard:
            try:
                state = self._load()
                if state and state.provider and state.model:
                    self._validate(state.provider, state.model)
                    return Provider(state.provider), state.model
            except ApplicationError:
                pass
            return Provider.MOCK, "mock-v1"

    def constructor_gateway(self, token: str | None):
        with self.guard:
            route = self._active_key(token, Role.INSTRUCTOR, Role.ADMINISTRATOR)
            if route is None:
                return create_gateway()
            _, provider, model, _, key = route
            return create_gateway(self._config(provider, model, key))

    @staticmethod
    def _config(provider: CloudProvider, model: str, key: SecretStr) -> GatewayConfig:
        return GatewayConfig(
            provider=Provider(provider),
            model=model,
            groq_api_key=key if provider == "groq" else None,
            google_api_key=key if provider == "gemini" else None,
            max_retries=0,
        )

    def probe(self, token: str | None, provider: CloudProvider, model: str) -> None:
        with self.guard:
            self._require(token, Role.ADMINISTRATOR)
            self._validate(provider, model)
            state = self._load(initialize=True)
            key = self._key(state, provider)
            if key is None:
                raise ApplicationError(_NO_KEY)
        try:
            gateway = create_gateway(self._config(provider, model, key))
            gateway.generate(
                GenerationRequest(
                    provider=Provider(provider),
                    model=model,
                    operation="text",
                    prompt="Synthetic connectivity check. Reply only with OK.",
                    parameters=GenerationParameters(
                        max_output_tokens=64, timeout_seconds=10
                    ),
                )
            )
        except GenerationError:
            raise ApplicationError("Перевірка з’єднання не вдалася.") from None
