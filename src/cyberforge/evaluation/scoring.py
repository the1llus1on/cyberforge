"""Production deterministic strategy over exact, validated immutable sources."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from .canonical import canonical_bytes, digest, reference_arithmetic
from .contracts import (
    CriterionEvaluationV1,
    EvaluationEvidenceV1,
    EvaluationResultV1,
    EvaluationSourceV1,
)
from .validation import evidence_projection, validate_sources

STRATEGY = "cyberforge-weighted-actions-v1"


def sealed(contract, fields, digest_field):
    return contract.model_validate_json(
        canonical_bytes(fields | {digest_field: digest(fields)})
    )


class ScoringService:
    """No authentication, storage, network or LLM dependency; caller owns sources."""

    def evidence(self, *, events, **sources) -> EvaluationEvidenceV1:
        attempt, manifest, rubric = (
            sources["attempt"],
            sources["manifest"],
            sources["rubric"],
        )
        source = EvaluationSourceV1(
            schema_version="evaluation-source-v1",
            publication_id=sources["publication_id"],
            version_id=sources["version_id"],
            manifest_schema_version=manifest.schema_version,
            manifest_digest=manifest.manifest_digest,
            snapshot=manifest.snapshot,
            rubric_id=rubric.rubric_id,
            rubric_schema_version=rubric.rubric_schema_version,
            registry_version=rubric.registry_version,
            rubric_semantics_version=rubric.semantics_version,
        )
        events = tuple(events)
        path, transition, criteria, observations = evidence_projection(
            attempt, events, rubric.criteria
        )
        value = sealed(
            EvaluationEvidenceV1,
            dict(
                schema_version="evaluation-evidence-v1",
                attempt=attempt,
                source=source,
                scoring_strategy=STRATEGY,
                events=events,
                event_count=len(events),
                terminal_sequence=len(events),
                events_digest=digest(events),
                path=path,
                transition=transition,
                criteria=criteria,
                critical_policy_status="NOT_CONFIGURED",
                critical_observations=observations,
            ),
            "evidence_digest",
        )
        validate_sources(value, **sources)
        return value

    def score(
        self,
        evidence: EvaluationEvidenceV1,
        *,
        result_id: UUID | None = None,
        evaluated_at: datetime | None = None,
    ) -> EvaluationResultV1:
        evidence = EvaluationEvidenceV1.model_validate_json(canonical_bytes(evidence))
        details = []
        for i, c in enumerate(evidence.criteria):
            descriptive = c.criterion.criterion_id == "transition.decision"
            score = (
                None if descriptive or not c.applicable else int(c.condition_satisfied)
            )
            details.append(
                CriterionEvaluationV1(
                    schema_version="criterion-evaluation-v1",
                    position=i,
                    criterion=c.criterion,
                    applicable=c.applicable,
                    outcome="DESCRIPTIVE"
                    if descriptive
                    else "NOT_APPLICABLE"
                    if score is None
                    else "MET"
                    if score
                    else "NOT_MET",
                    score=score,
                    weighted_contribution=None
                    if score is None
                    else c.criterion.weight
                    if score
                    else Decimal(0),
                    supporting_event_refs=c.supporting_event_refs,
                    descriptive_transition=evidence.transition if descriptive else None,
                )
            )
        numerator, denominator, percent = reference_arithmetic(
            tuple((c.criterion.weight, c.score) for c in details if c.score is not None)
        )
        fields = {
            k: getattr(evidence, k)
            for k in EvaluationResultV1.model_fields
            if k in EvaluationEvidenceV1.model_fields and k != "schema_version"
        }
        fields.update(
            schema_version="evaluation-result-v1",
            result_id=result_id or uuid4(),
            criteria=tuple(details),
            status="SCORED" if percent is not None else "UNSCORABLE",
            reason_code=None
            if percent is not None
            else "NO_APPLICABLE_NUMERICAL_CRITERIA",
            weighted_numerator=numerator,
            weighted_denominator=denominator,
            score_percent=percent,
            evaluated_at=evaluated_at or datetime.now(UTC),
        )
        return sealed(EvaluationResultV1, fields, "result_digest")


def numerical_paths_ready(rubric) -> bool:
    """Prospective publication rule only; historical rubric loading is unchanged."""
    return rubric is not None and all(
        any(
            c.criterion_id != "transition.decision"
            and c.applicability in ("all_attempts", path)
            for c in rubric.criteria
        )
        for path in ("web_not_visited", "web_visited")
    )
