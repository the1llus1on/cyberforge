"""D12-09 interface kept behind the authorized provider service."""

from typing import Literal, Protocol

from pydantic import SecretStr

CloudProvider = Literal["groq", "gemini"]


class SecretStoreError(RuntimeError):
    """An unavailable or failed vault operation, with no native secret data."""


class SecretStore(Protocol):
    """Credential operations scoped to one stable release channel and profile."""

    def read(self, provider: CloudProvider) -> SecretStr | None:
        """Read a secret for an authorized adapter or return None if absent."""
        ...

    def write(self, provider: CloudProvider, secret: SecretStr) -> None:
        """Save or replace a secret in the operating system vault."""
        ...

    def delete(self, provider: CloudProvider) -> None:
        """Remove the provider entry if it exists."""
        ...
