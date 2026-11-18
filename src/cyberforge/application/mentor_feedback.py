"""Grounded optional Mentor selection with immutable, independently saved feedback."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import insert, select

from cyberforge.agents.contracts import MentorInputV1
from cyberforge.agents.specialized import MentorAgent
from cyberforge.application.evaluations import EvaluationFailure, row_matches
from cyberforge.evaluation.canonical import canonical_bytes, value_tree
from cyberforge.evaluation.contracts import LocalMentorFeedbackV1
from cyberforge.evaluation.facts import (
    OBJECTIVE,
    deterministic_explanation,
    project_facts,
    validate_feedback_against_result,
)
from cyberforge.evaluation.scoring import sealed
from cyberforge.llm.contracts import ErrorCategory, Provider
from cyberforge.persistence.models import MentorFeedbackRecord


def feedback_columns(value):
    fields = {
        k: v
        for k, v in value_tree(value).items()
        if k in MentorFeedbackRecord.__table__.columns
    }
    fields.update(
        id=str(value.feedback_id), feedback_json=canonical_bytes(value).decode()
    )
    return fields


class MentorFeedbackService:
    def __init__(self, evaluations, gateway):
        self.evaluations, self.gateway = evaluations, gateway

    def _read(self, db, result):
        row = db.scalar(
            select(MentorFeedbackRecord).where(
                MentorFeedbackRecord.result_id == str(result.result_id)
            )
        )
        return self._validate_row(row, result)

    @staticmethod
    def _validate_row(row, result):
        if row is None:
            return None
        try:
            value = LocalMentorFeedbackV1.model_validate_json(row.feedback_json)
            validate_feedback_against_result(value, result)
            if (
                not row_matches(row, feedback_columns(value))
                or value.created_at < result.evaluated_at
            ):
                raise ValueError("feedback_projection_time")
            return value
        except (ValueError, TypeError, AttributeError, KeyError):
            raise EvaluationFailure(
                "STORED_FEEDBACK_INTEGRITY_ERROR",
                operation="feedback",
                attempt_id=result.attempt.attempt_id,
                result_id=result.result_id,
                reason="FEEDBACK_INTEGRITY_MISMATCH",
            ) from None

    def read(self, token, attempt_id):
        ev = self.evaluations
        aid = ev._syntax(attempt_id)
        with ev.transaction(operation="feedback") as db:
            result = ev._read(db, ev._owned(db, token, aid), operation="feedback")
            return self._read(db, result) if result else None

    def _build(self, result):
        facts, topics = project_facts(result)
        explanation = deterministic_explanation(result)
        mode, provider, model = "DETERMINISTIC", None, None
        reason = "UNSCORABLE" if result.status == "UNSCORABLE" else "CLOUD_DISABLED"
        if result.status == "SCORED" and self.gateway.config.provider != Provider.MOCK:
            reason = "PROVIDER_FAILURE"
            try:
                source = MentorInputV1(
                    synthetic=True,
                    objective=OBJECTIVE,
                    facts=facts,
                    permitted_topics=topics,
                    result=explanation.result,
                )
                selected = MentorAgent(self.gateway).run(source)
                if selected.status != "failed" and selected.draft is not None:
                    explanation = selected.draft
                    mode, reason = "MODEL_SELECTION", None
                    telemetry = selected.telemetry[-1]
                    provider, model = (
                        telemetry.provider.value,
                        telemetry.effective_model,
                    )
                elif selected.error in {
                    ErrorCategory.VALIDATION,
                    ErrorCategory.REQUEST,
                    ErrorCategory.SCHEMA,
                }:
                    reason = "INVALID_SELECTION"
            except Exception:
                # No raw provider details cross into UI or historical feedback.
                pass
        fields = dict(
            schema_version="local-mentor-feedback-v1",
            feedback_id=uuid4(),
            result_id=result.result_id,
            result_digest=result.result_digest,
            evidence_digest=result.evidence_digest,
            evaluation_status=result.status,
            locale="uk-UA",
            fact_catalog_version="educational-facts-v1",
            synthetic=True,
            objective=OBJECTIVE,
            facts=facts,
            permitted_topics=topics,
            mode=mode,
            fallback_reason=reason,
            provider=provider,
            model=model,
            explanation=explanation,
            created_at=datetime.now(UTC),
        )
        try:
            value = sealed(LocalMentorFeedbackV1, fields, "feedback_digest")
            validate_feedback_against_result(value, result)
            return value
        except (ValueError, TypeError, AttributeError, KeyError):
            fields.update(
                mode="DETERMINISTIC",
                fallback_reason="UNSCORABLE"
                if result.status == "UNSCORABLE"
                else "INVALID_SELECTION",
                provider=None,
                model=None,
                explanation=deterministic_explanation(result),
            )
            return sealed(LocalMentorFeedbackV1, fields, "feedback_digest")

    def generate(self, token, attempt_id):
        ev = self.evaluations
        aid = ev._syntax(attempt_id)
        # Scoring is committed independently before any provider invocation.
        result = ev.evaluate(token, aid)
        existing = self.read(token, aid)
        if existing is not None:
            return existing
        candidate = self._build(result)
        # Reauthenticate after slow generation; a concurrent winner is authoritative.
        with ev.transaction(write=True, operation="feedback") as db:
            current = ev._read(db, ev._owned(db, token, aid), operation="feedback")
            if current is None or current != result:
                raise EvaluationFailure(
                    "STORED_EVALUATION_INTEGRITY_ERROR",
                    operation="feedback",
                    attempt_id=aid,
                    result_id=UUID(str(result.result_id)),
                    reason="RESULT_BINDING_MISMATCH",
                )
            existing = self._read(db, current)
            if existing is not None:
                return existing
            validate_feedback_against_result(candidate, current)
            db.execute(
                insert(MentorFeedbackRecord).values(**feedback_columns(candidate))
            )
            return candidate
