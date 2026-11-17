"""Frozen candidates from the owner-reviewed WP1 field specification."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from cyberforge.agents.contracts import (
    ExplanationV1,
    FactV1,
    Topic,
    resource_id,
    safe_text,
)
from cyberforge.learning.contracts import AttemptEventV1, ScenarioAttemptV1
from cyberforge.scenario_integration.contracts import (
    REGISTRY,
    Applicability,
    Digest,
    Identifier,
    Phase,
    ReviewedSourcesV1,
)

from .canonical import (
    bounded_decimal,
    bounded_decimal_input,
    canonical_bytes,
    digest,
    historical_weight,
    reference_arithmetic,
)

CriterionId = Literal[
    "email.sender",
    "email.link",
    "email.report",
    "transition.safe_decline",
    "transition.decision",
    "web.address",
    "web.leave",
    "web.report",
]
Exact = Annotated[
    Decimal,
    Field(allow_inf_nan=False, ge=0, le=70000),
    BeforeValidator(bounded_decimal_input),
    AfterValidator(bounded_decimal),
]
Weight = Annotated[
    Decimal,
    Field(allow_inf_nan=False, gt=0, le=10000),
    BeforeValidator(bounded_decimal_input),
    AfterValidator(bounded_decimal),
]
Percentage = Annotated[
    Decimal,
    Field(allow_inf_nan=False, ge=0, le=100),
    BeforeValidator(bounded_decimal_input),
    AfterValidator(bounded_decimal),
]
Criteria = Annotated[tuple, Field(min_length=1, max_length=8)]


class Closed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
        hide_input_in_errors=True,
    )

    @classmethod
    def model_validate_json(cls, json_data, **kwargs):
        import json

        from .canonical import _unique

        raw = json_data.encode() if isinstance(json_data, str) else bytes(json_data)
        json.loads(
            raw, object_pairs_hook=_unique, parse_constant=lambda _: float("nan")
        )
        kwargs["strict"] = True
        value = super().model_validate_json(raw, **kwargs)
        if canonical_bytes(value) != raw:
            raise ValueError("noncanonical_json")
        return value

    @model_validator(mode="after")
    def utc_fields(self) -> Self:
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, datetime) and (
                value.utcoffset() is None or value.utcoffset().total_seconds() != 0
            ):
                raise ValueError("utc_required")
        return self


class EvaluationSourceV1(Closed):
    schema_version: Literal["evaluation-source-v1"]
    publication_id: Identifier
    version_id: Identifier
    manifest_schema_version: Literal["scenario-publication-v1"]
    manifest_digest: Digest
    snapshot: ReviewedSourcesV1
    rubric_id: str
    rubric_schema_version: Literal["rubric-definition-v1"]
    registry_version: Literal["criterion-registry-v1"]
    rubric_semantics_version: Literal["rubric-declarations-v1"]

    @model_validator(mode="after")
    def valid(self) -> Self:
        resource_id(self.rubric_id)
        return self


class EvaluationCriterionSnapshotV1(Closed):
    schema_version: Literal["evaluation-criterion-snapshot-v1"]
    criterion_id: CriterionId
    label: str
    description: str
    phase: Phase
    weight: Weight
    applicability: Applicability
    evidence_actions: tuple[str, ...]
    critical_action: Literal[None]

    @model_validator(mode="after")
    def registered(self) -> Self:
        spec = REGISTRY[self.criterion_id]
        if (self.label, self.description, self.phase, self.evidence_actions) != (
            spec.label,
            spec.description,
            spec.phase,
            spec.actions,
        ) or self.applicability not in spec.applicability:
            raise ValueError("criterion_registry")
        return self

    @classmethod
    def from_declaration(cls, value):
        data = value.model_dump()
        data["weight"] = historical_weight(value.weight)
        return cls(schema_version="evaluation-criterion-snapshot-v1", **data)


class EvaluationEventReferenceV1(Closed):
    event_id: UUID
    sequence: Identifier


def references(values):
    if len({r.event_id for r in values}) != len(values) or [
        r.sequence for r in values
    ] != sorted({r.sequence for r in values}):
        raise ValueError("reference_order_identity")


class CompletedPathV1(Closed):
    schema_version: Literal["completed-path-v1"]
    kind: Literal["SAFE_DECLINE", "WEB_VISITED"]
    event_refs: tuple[EvaluationEventReferenceV1, ...]

    @model_validator(mode="after")
    def valid(self) -> Self:
        references(self.event_refs)
        if len(self.event_refs) != (2 if self.kind == "SAFE_DECLINE" else 3):
            raise ValueError("path_references")
        return self


class TransitionDecisionV1(Closed):
    schema_version: Literal["transition-decision-v1"]
    final_action_id: Literal["decline", "open_internal"]
    event_refs: tuple[EvaluationEventReferenceV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self) -> Self:
        references(self.event_refs)
        return self


class CriterionEvidenceV1(Closed):
    schema_version: Literal["criterion-evidence-v1"]
    criterion: EvaluationCriterionSnapshotV1
    applicable: bool
    condition_satisfied: bool | None
    supporting_event_refs: tuple[EvaluationEventReferenceV1, ...]

    @model_validator(mode="after")
    def valid(self) -> Self:
        references(self.supporting_event_refs)
        descriptive = self.criterion.criterion_id == "transition.decision"
        if descriptive:
            if not self.applicable or self.condition_satisfied is not None:
                raise ValueError("descriptive_evidence")
        elif self.applicable:
            if type(
                self.condition_satisfied
            ) is not bool or self.condition_satisfied != bool(
                self.supporting_event_refs
            ):
                raise ValueError("numerical_evidence")
        elif self.condition_satisfied is not None or self.supporting_event_refs:
            raise ValueError("nonapplicable_evidence")
        return self


class CriticalObservationV1(Closed):
    schema_version: Literal["critical-observation-v1"]
    event_ref: EvaluationEventReferenceV1
    surface: Literal["web"]
    action_id: Literal["confirm", "submit_synthetic"]
    component_id: str
    provenance: Literal["authored_component"]
    observed_at: AwareDatetime
    critical_policy_status: Literal["NOT_CONFIGURED"]

    @model_validator(mode="after")
    def valid(self) -> Self:
        resource_id(self.component_id)
        return self


class EvaluationEvidenceV1(Closed):
    schema_version: Literal["evaluation-evidence-v1"]
    attempt: ScenarioAttemptV1
    source: EvaluationSourceV1
    scoring_strategy: Literal["cyberforge-weighted-actions-v1"]
    events: tuple[AttemptEventV1, ...] = Field(min_length=1)
    event_count: Identifier
    terminal_sequence: Identifier
    events_digest: Digest
    path: CompletedPathV1
    transition: TransitionDecisionV1
    criteria: tuple[CriterionEvidenceV1, ...] = Field(min_length=1, max_length=8)
    critical_policy_status: Literal["NOT_CONFIGURED"]
    critical_observations: tuple[CriticalObservationV1, ...]
    evidence_digest: Digest

    @model_validator(mode="after")
    def valid(self) -> Self:
        from .validation import validate_evidence_structure

        validate_evidence_structure(self)
        return self


class CriterionEvaluationV1(Closed):
    schema_version: Literal["criterion-evaluation-v1"]
    position: Annotated[int, Field(strict=True, ge=0, le=7)]
    criterion: EvaluationCriterionSnapshotV1
    applicable: bool
    outcome: Literal["MET", "NOT_MET", "NOT_APPLICABLE", "DESCRIPTIVE"]
    score: Annotated[int, Field(strict=True, ge=0, le=1)] | None
    weighted_contribution: Exact | None
    supporting_event_refs: tuple[EvaluationEventReferenceV1, ...]
    descriptive_transition: TransitionDecisionV1 | None

    @model_validator(mode="after")
    def valid(self) -> Self:
        references(self.supporting_event_refs)
        if self.criterion.criterion_id == "transition.decision":
            valid = (
                self.outcome == "DESCRIPTIVE"
                and self.applicable
                and self.score is None
                and self.weighted_contribution is None
                and self.descriptive_transition is not None
                and self.supporting_event_refs == self.descriptive_transition.event_refs
            )
        elif not self.applicable:
            valid = (
                self.outcome == "NOT_APPLICABLE"
                and self.score is None
                and self.weighted_contribution is None
                and not self.supporting_event_refs
                and self.descriptive_transition is None
            )
        else:
            valid = (
                self.score in (0, 1)
                and self.outcome == ("MET" if self.score == 1 else "NOT_MET")
                and self.weighted_contribution
                == (self.criterion.weight if self.score == 1 else Decimal(0))
                and bool(self.supporting_event_refs) == bool(self.score)
                and self.descriptive_transition is None
            )
        if not valid:
            raise ValueError("criterion_outcome")
        return self


class EvaluationResultV1(Closed):
    schema_version: Literal["evaluation-result-v1"]
    result_id: UUID
    attempt: ScenarioAttemptV1
    source: EvaluationSourceV1
    scoring_strategy: Literal["cyberforge-weighted-actions-v1"]
    event_count: Identifier
    terminal_sequence: Identifier
    events_digest: Digest
    evidence_digest: Digest
    path: CompletedPathV1
    transition: TransitionDecisionV1
    criteria: tuple[CriterionEvaluationV1, ...] = Field(min_length=1, max_length=8)
    critical_policy_status: Literal["NOT_CONFIGURED"]
    critical_observations: tuple[CriticalObservationV1, ...]
    status: Literal["SCORED", "UNSCORABLE"]
    reason_code: Literal["NO_APPLICABLE_NUMERICAL_CRITERIA"] | None
    weighted_numerator: Exact
    weighted_denominator: Exact
    score_percent: Percentage | None
    evaluated_at: AwareDatetime
    result_digest: Digest

    @model_validator(mode="after")
    def valid(self) -> Self:
        from .validation import validate_binding, validate_criterion_order

        validate_binding(self.attempt, self.source)
        validate_criterion_order(self.criteria)
        if [c.position for c in self.criteria] != list(
            range(len(self.criteria))
        ) or any(
            c.descriptive_transition != self.transition
            for c in self.criteria
            if c.outcome == "DESCRIPTIVE"
        ):
            raise ValueError("result_details")
        totals = reference_arithmetic(
            tuple(
                (c.criterion.weight, c.score)
                for c in self.criteria
                if c.score is not None
            )
        )
        if totals != (
            self.weighted_numerator,
            self.weighted_denominator,
            self.score_percent,
        ):
            raise ValueError("result_arithmetic")
        if (self.status, self.reason_code) != (
            ("SCORED", None)
            if totals[2] is not None
            else ("UNSCORABLE", "NO_APPLICABLE_NUMERICAL_CRITERIA")
        ):
            raise ValueError("result_status")
        if (
            self.event_count != self.terminal_sequence
            or self.terminal_sequence != self.attempt.last_event_sequence
            or digest(self, exclude="result_digest") != self.result_digest
        ):
            raise ValueError("result_digest_sequence")
        return self


class LocalMentorFeedbackV1(Closed):
    schema_version: Literal["local-mentor-feedback-v1"]
    feedback_id: UUID
    result_id: UUID
    result_digest: Digest
    evidence_digest: Digest
    evaluation_status: Literal["SCORED", "UNSCORABLE"]
    locale: Literal["uk-UA"]
    fact_catalog_version: Literal["educational-facts-v1"]
    synthetic: Literal[True]
    objective: str = Field(min_length=1, max_length=2000)
    facts: tuple[FactV1, ...] = Field(max_length=24)
    permitted_topics: tuple[Topic, ...] = Field(min_length=1, max_length=4)
    mode: Literal["DETERMINISTIC", "MODEL_SELECTION"]
    fallback_reason: (
        Literal["UNSCORABLE", "CLOUD_DISABLED", "PROVIDER_FAILURE", "INVALID_SELECTION"]
        | None
    )
    provider: Literal["mock", "groq", "gemini"] | None
    model: str | None
    explanation: ExplanationV1
    created_at: AwareDatetime
    feedback_digest: Digest

    @field_validator("explanation", mode="after")
    @classmethod
    def fresh_legacy_explanation(cls, value):
        # Phase5 models predate revalidate_instances. Copy through their accepted
        # JSON validator so even a forged instance cannot retain mutable values.
        if isinstance(value, ExplanationV1):
            try:
                return ExplanationV1.model_validate_json(canonical_bytes(value))
            except (AttributeError, TypeError) as exc:
                raise ValueError("invalid_legacy_explanation") from exc
        return value

    @model_validator(mode="after")
    def valid(self) -> Self:
        from .facts import validate_feedback

        safe_text(self.objective)
        validate_feedback(self)
        if digest(self, exclude="feedback_digest") != self.feedback_digest:
            raise ValueError("feedback_digest")
        return self


class EvaluationErrorV1(Closed):
    schema_version: Literal["evaluation-error-v1"]
    operation: Literal["evaluate", "read", "feedback", "analytics_read"]
    code: Literal[
        "ACCESS_DENIED",
        "ATTEMPT_NOT_COMPLETED",
        "UNSUPPORTED_VERSION",
        "INVALID_RUBRIC",
        "INVALID_EVIDENCE",
        "STORAGE_BUSY",
        "STORAGE_UNAVAILABLE",
        "SOURCE_UNAVAILABLE",
        "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
        "STORED_EVALUATION_INTEGRITY_ERROR",
        "STORED_FEEDBACK_INTEGRITY_ERROR",
        "STORAGE_FAILURE",
    ]
    retryable: bool
    correlation_id: UUID
    attempt_id: UUID | None
    result_id: UUID | None
    integrity_reason: (
        Literal[
            "IMMUTABLE_SOURCE_MISSING",
            "IMMUTABLE_SOURCE_INVALID",
            "RESULT_DIGEST_MISMATCH",
            "RESULT_BINDING_MISMATCH",
            "EVIDENCE_BINDING_MISMATCH",
            "CRITERION_DETAILS_INVALID",
            "ARITHMETIC_MISMATCH",
            "FEEDBACK_INTEGRITY_MISMATCH",
        ]
        | None
    )

    @model_validator(mode="after")
    def valid(self) -> Self:
        reasons = {
            "IMMUTABLE_SOURCE_INTEGRITY_ERROR": {
                "IMMUTABLE_SOURCE_MISSING",
                "IMMUTABLE_SOURCE_INVALID",
            },
            "STORED_EVALUATION_INTEGRITY_ERROR": {
                "IMMUTABLE_SOURCE_MISSING",
                "IMMUTABLE_SOURCE_INVALID",
                "RESULT_DIGEST_MISMATCH",
                "RESULT_BINDING_MISMATCH",
                "EVIDENCE_BINDING_MISMATCH",
                "CRITERION_DETAILS_INVALID",
                "ARITHMETIC_MISMATCH",
            },
            "STORED_FEEDBACK_INTEGRITY_ERROR": {"FEEDBACK_INTEGRITY_MISMATCH"},
        }
        if self.retryable != (
            self.code in {"STORAGE_BUSY", "STORAGE_UNAVAILABLE", "SOURCE_UNAVAILABLE"}
        ) or self.integrity_reason not in reasons.get(self.code, {None}):
            raise ValueError("error_semantics")
        if self.code == "ACCESS_DENIED" and (
            self.attempt_id is not None or self.result_id is not None
        ):
            raise ValueError("error_disclosure")
        return self
