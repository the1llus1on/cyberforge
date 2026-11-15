"""Explicit configuration loading without mutating the process environment."""

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator

from cyberforge.llm.contracts import (
    Contract,
    ErrorCategory,
    GenerationError,
    GenerationParameters,
    Provider,
)

APPROVED_MODELS = {
    Provider.MOCK: {"mock-v1"},
    Provider.GEMINI: {"gemini-4-hydrogen", "gemini-3.8-flash", "gemini-3.5-flash-lite"},
    Provider.GROQ: {"openai/gpt-oss-120b"},
}
THINKING_LEVELS = {
    "gemini-4-hydrogen": {"low", "medium", "high", "xhigh"},
    "gemini-3.8-flash": {"low", "medium", "high"},
    "gemini-3.5-flash-lite": {"minimal", "low", "medium", "high"},
    "openai/gpt-oss-120b": {"low", "medium", "high"},
    "mock-v1": {"minimal", "low", "medium", "high"},
}


def validate_selection(provider: Provider, model: str, thinking: str | None) -> None:
    if model not in APPROVED_MODELS[provider]:
        raise GenerationError(ErrorCategory.CONFIGURATION)
    if thinking is not None and thinking not in THINKING_LEVELS[model]:
        raise GenerationError(ErrorCategory.CONFIGURATION)


class BackupConfig(Contract):
    provider: Provider
    model: str
    enabled: bool = False
    access_verified: bool = False

    @model_validator(mode="after")
    def validate_backup(self):
        if (
            self.provider == Provider.MOCK
            or self.model not in APPROVED_MODELS[self.provider]
        ):
            raise ValueError("Backup must name an approved cloud model")
        if self.enabled and not self.access_verified:
            raise ValueError("Verify backup access before enabling fallback")
        return self


class RateLimits(Contract):
    rpm: int | None = Field(default=None, ge=1)
    tpm: int | None = Field(default=None, ge=1)
    rpd: int | None = Field(default=None, ge=1)
    tpd: int | None = Field(default=None, ge=1)


class GatewayConfig(Contract):
    provider: Provider = Provider.MOCK
    model: str = "mock-v1"
    parameters: GenerationParameters = Field(default_factory=GenerationParameters)
    email_max_output_tokens: int | None = Field(default=None, ge=1)
    web_max_output_tokens: int | None = Field(default=None, ge=1)
    google_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    groq_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    max_retries: int = Field(default=2, ge=0, le=3)
    max_backoff_seconds: float = Field(default=10, gt=0, le=60)
    fallback_to_groq: bool = False
    backup: BackupConfig | None = None
    # Keys: provider name and/or provider:model. Both budgets apply.
    limits: dict[str, RateLimits] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_routing(self):
        if self.backup is not None:
            if self.fallback_to_groq:
                raise ValueError("Do not combine legacy fallback and explicit backup")
            if self.backup.enabled and (
                self.provider == Provider.MOCK
                or (self.provider, self.model)
                == (self.backup.provider, self.backup.model)
            ):
                raise ValueError("Fallback requires distinct cloud primary and backup")
        return self

    @field_validator("limits")
    @classmethod
    def validate_limit_keys(cls, value: dict[str, RateLimits]) -> dict[str, RateLimits]:
        allowed = {provider.value for provider in Provider} | {
            f"{provider.value}:{model}"
            for provider, models in APPROVED_MODELS.items()
            for model in models
        }
        if set(value) - allowed:
            raise ValueError("Unknown provider/model quota key")
        return value


def load_config(
    env_file: Path = Path(".env"), environ: Mapping[str, str] | None = None
) -> GatewayConfig:
    """Environment wins, including empty values; interpolation is disabled."""
    try:
        values = {
            **dotenv_values(env_file, interpolate=False),
            **(os.environ if environ is None else environ),
        }
        fields = {
            "provider": "CYBERFORGE_LLM_PROVIDER",
            "model": "CYBERFORGE_LLM_MODEL",
            "google_api_key": "GOOGLE_API_KEY",
            "groq_api_key": "GROQ_API_KEY",
            "max_retries": "CYBERFORGE_LLM_MAX_RETRIES",
            "email_max_output_tokens": "CYBERFORGE_EMAIL_MAX_OUTPUT_TOKENS",
            "web_max_output_tokens": "CYBERFORGE_WEB_MAX_OUTPUT_TOKENS",
            "fallback_to_groq": "CYBERFORGE_LLM_FALLBACK",
        }
        data = {key: values[name] for key, name in fields.items() if values.get(name)}
        if values.get("CYBERFORGE_LLM_PARAMETERS"):
            data["parameters"] = GenerationParameters.model_validate_json(
                values["CYBERFORGE_LLM_PARAMETERS"]
            )
        if values.get("CYBERFORGE_LLM_BACKUP"):
            data["backup"] = BackupConfig.model_validate_json(
                values["CYBERFORGE_LLM_BACKUP"]
            )
        if values.get("CYBERFORGE_LLM_LIMITS"):
            from pydantic import TypeAdapter

            data["limits"] = TypeAdapter(dict[str, RateLimits]).validate_json(
                values["CYBERFORGE_LLM_LIMITS"]
            )
        config = GatewayConfig.model_validate(data)
        validate_selection(config.provider, config.model, config.parameters.thinking)
        return config
    except (OSError, ValueError, ValidationError):
        raise GenerationError(ErrorCategory.CONFIGURATION) from None
