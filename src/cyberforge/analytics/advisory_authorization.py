"""Local policy evidence and the values bound to a D12-10 preview."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from cyberforge.llm.secret_store import CloudProvider

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
LocalLabel = Annotated[str, Field(min_length=1, max_length=200)]


class _PolicyRecord(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


class ProviderPrivacyProfileV1(_PolicyRecord):
    profile_id: LocalLabel
    credential_revision: LocalLabel
    provider: CloudProvider
    account_reference: LocalLabel
    endpoint: LocalLabel
    model: LocalLabel
    mode: LocalLabel


class AdvisoryPolicyEvidenceV1(_PolicyRecord):
    schema_version: Literal["advisory-policy-evidence-v1"]
    purpose: Literal["instructor-topic-advisory"]
    data_class: Literal["real", "synthetic"]
    scope_digest: Digest
    provider_profile: ProviderPrivacyProfileV1
    organization_decision: LocalLabel
    provider_privacy_review: LocalLabel
    responsible_party: LocalLabel
    assessed_at: AwareDatetime
    expires_at: AwareDatetime
    revoked: bool
    residual_linkability_accepted: bool

    @model_validator(mode="after")
    def valid_interval(self) -> Self:
        if self.assessed_at >= self.expires_at:
            raise ValueError("invalid_policy_interval")
        return self

    def permits(
        self,
        *,
        scope_digest: str,
        provider_profile: ProviderPrivacyProfileV1,
        data_class: Literal["real", "synthetic"],
        now: datetime,
    ) -> bool:
        """Compare with trusted local evidence after independent authorization."""
        return (
            now.utcoffset() is not None
            and self.assessed_at <= now < self.expires_at
            and not self.revoked
            and self.residual_linkability_accepted
            and self.scope_digest == scope_digest
            and self.provider_profile == provider_profile
            and self.data_class == data_class
        )


@dataclass(frozen=True, repr=False)
class AdvisoryPreviewBinding:
    """Equality covers the entire local comparison at dispatch and display."""

    session_reference: str
    ui_generation: int
    scope_digest: str
    source_digest: str
    policy: AdvisoryPolicyEvidenceV1
    request_digest: str
