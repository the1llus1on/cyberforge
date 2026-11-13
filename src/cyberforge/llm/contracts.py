"""Versioned contracts independent of provider SDKs and scenario persistence."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Provider(StrEnum):
    MOCK = "mock"
    GEMINI = "gemini"
    GROQ = "groq"


class ErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMIT = "rate_limit"
    BUDGET = "budget_exhausted"
    AUTHORIZATION = "authorization"
    MISSING_CREDENTIALS = "missing_credentials"
    CONFIGURATION = "configuration"
    SCHEMA = "unsupported_schema"
    VALIDATION = "validation"
    SAFETY = "safety_refusal"
    REQUEST = "invalid_request"
    TRANSPORT = "transport"


class GenerationError(Exception):
    """Only normalized categories cross the integration boundary."""

    def __init__(self, category: ErrorCategory, retry_after: float | None = None):
        self.category = category
        self.retry_after = retry_after
        super().__init__(category.value)


class GenerationParameters(Contract):
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_output_tokens: int = Field(default=512, ge=1, le=8192)
    thinking: Literal["minimal", "low", "medium", "high"] | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=120)


class GenerationRequest(Contract):
    # Callers must construct synthetic input, never pass account/scoring records.
    prompt: str = Field(min_length=1, max_length=24000, repr=False, exclude=True)
    synthetic: Literal[True]
    provider: Provider = Provider.MOCK
    model: str = "mock-v1"
    operation: Literal["text", "structured"] = "text"
    prompt_version: str = Field(default="connectivity-v1", pattern=r"^[\w.-]{1,64}$")
    schema_version: str | None = Field(default=None, pattern=r"^[\w.-]{1,64}$")
    parameters: GenerationParameters = Field(default_factory=GenerationParameters)


class Usage(Contract):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)


class ProviderResponse(Contract):
    text: str = Field(repr=False, exclude=True)
    actual_model: str | None = None
    usage: Usage = Field(default_factory=Usage)


class GenerationTelemetry(Contract):
    provider: Provider
    requested_model: str
    actual_model: str | None = None
    operation: Literal["text", "structured"]
    prompt_version: str
    schema_version: str | None
    requested_parameters: GenerationParameters
    effective_parameters: GenerationParameters
    schema_projection: Literal["groq-artifact-v1-local-resource-id"] | None = None
    elapsed_seconds: float = Field(ge=0)
    usage: Usage = Field(default_factory=Usage)
    status: Literal["success", "error"]
    retry_count: int = Field(default=0, ge=0)
    fallback: bool = False
    error: ErrorCategory | None = None
    local_validation: Literal["passed", "failed"] | None = None


class GenerationResult(Contract):
    text: str = Field(repr=False, exclude=True)
    structured: BaseModel | None = Field(default=None, repr=False, exclude=True)
    telemetry: GenerationTelemetry


class ScenarioContextV1(Contract):
    """Synthetic consistency anchor; carries no learner/account identifiers."""

    schema_version: Literal["scenario-context-v1"]
    organization: str
    sender_name: str
    premise: str
    internal_resource_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class EmailArtifactV1(Contract):
    schema_version: Literal["email-artifact-v1"]
    context: ScenarioContextV1
    subject: str
    body_text: str


class WebArtifactV1(Contract):
    """Plain content slots only; no executable markup or navigable URL."""

    schema_version: Literal["web-artifact-v1"]
    context: ScenarioContextV1
    heading: str
    body_text: str
    action_label: str
