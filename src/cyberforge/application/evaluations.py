"""Authorized atomic evaluations and the single stored integrity read path."""

from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from cyberforge.application.learner_attempts import attempt_value, event_value
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.evaluation.canonical import canonical_bytes, value_tree
from cyberforge.evaluation.contracts import (
    CriterionEvaluationV1,
    EvaluationErrorV1,
    EvaluationEvidenceV1,
    EvaluationResultV1,
)
from cyberforge.evaluation.scoring import ScoringService
from cyberforge.evaluation.validation import validate_stored_projection
from cyberforge.learning.contracts import ScenarioAttemptV1
from cyberforge.persistence.models import (
    AttemptEventRecord,
    EvaluationCriterionRecord,
    EvaluationResultRecord,
    ScenarioAttemptRecord,
    ScenarioPublication,
    ScenarioRecord,
    ScenarioVersion,
)

MESSAGES = {
    "ACCESS_DENIED": "Доступ до результатів обмежено. Увійдіть як учень.",
    "ATTEMPT_NOT_COMPLETED": "Оцінювання доступне лише для завершеної спроби.",
    "STORED_EVALUATION_INTEGRITY_ERROR": (
        "Порушено цілісність збереженої оцінки. Результат недоступний."
    ),
    "STORED_FEEDBACK_INTEGRITY_ERROR": (
        "Порушено цілісність пояснення. Пояснення недоступне."
    ),
    "IMMUTABLE_SOURCE_INTEGRITY_ERROR": "Порушено цілісність джерел спроби.",
    "INVALID_EVIDENCE": "Події спроби не відповідають правилам оцінювання.",
    "STORAGE_BUSY": "База даних зайнята. Повторіть спробу.",
    "STORAGE_UNAVAILABLE": "База даних недоступна. Повторіть спробу.",
    "STORAGE_FAILURE": "Не вдалося зберегти результат.",
}


class EvaluationFailure(ApplicationError):
    def __init__(
        self, code, *, operation="read", attempt_id=None, result_id=None, reason=None
    ):
        self.error = EvaluationErrorV1(
            schema_version="evaluation-error-v1",
            operation=operation,
            code=code,
            retryable=code
            in {"STORAGE_BUSY", "STORAGE_UNAVAILABLE", "SOURCE_UNAVAILABLE"},
            correlation_id=uuid4(),
            attempt_id=attempt_id,
            result_id=result_id,
            integrity_reason=reason,
        )
        super().__init__(MESSAGES.get(code, "Результат недоступний."))


def safe_uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def result_columns(result, evidence):
    r = value_tree(result)
    a, s = r["attempt"], r["source"]
    fields = {
        k: r[k]
        for k in (
            "scoring_strategy",
            "status",
            "reason_code",
            "weighted_numerator",
            "weighted_denominator",
            "score_percent",
            "event_count",
            "terminal_sequence",
            "events_digest",
            "evidence_digest",
            "result_digest",
            "evaluated_at",
        )
    }
    fields.update(
        id=r["result_id"],
        attempt_id=a["attempt_id"],
        learner_id=a["learner_id"],
        scenario_id=a["scenario_id"],
        publication_id=s["publication_id"],
        version_id=s["version_id"],
        rubric_version_id=s["version_id"],
        scenario_version=a["scenario_version"],
        rubric_id=s["rubric_id"],
        rubric_revision=s["snapshot"]["rubric_revision"],
        manifest_digest=s["manifest_digest"],
        rubric_digest=s["snapshot"]["rubric_digest"],
        attempt_revision=a["revision"],
        result_json=canonical_bytes(result).decode(),
        evidence_json=canonical_bytes(evidence).decode(),
    )
    return fields


def criterion_columns(result_id, c):
    return dict(
        result_id=str(result_id),
        criterion_id=c.criterion.criterion_id,
        position=c.position,
        applicable=c.applicable,
        outcome=c.outcome,
        score=c.score,
        weight=value_tree(c.criterion)["weight"],
        weighted_contribution=value_tree(c)["weighted_contribution"],
        criterion_json=canonical_bytes(c).decode(),
    )


def row_matches(row, fields):
    return all(getattr(row, k) == v for k, v in fields.items())


class StoredEvaluationIntegrityValidation:
    """Read-only validation, shared by retry, learner and Mentor consumers.

    Future analytics must authorize its own caller before invoking this path.
    No evaluation identity/timestamp is created and no historical row is repaired.
    """

    def validate(self, row, details, *, sources, events):
        result = EvaluationResultV1.model_validate_json(row.result_json)
        evidence = EvaluationEvidenceV1.model_validate_json(row.evidence_json)
        parsed = tuple(
            CriterionEvaluationV1.model_validate_json(d.criterion_json) for d in details
        )
        if evidence.events != events or not row_matches(
            row, result_columns(result, evidence)
        ):
            raise ValueError("stored_projection")
        if len(details) != len(result.criteria) or any(
            not row_matches(d, criterion_columns(result.result_id, c))
            for d, c in zip(details, result.criteria, strict=True)
        ):
            raise ValueError("stored_detail_projection")
        if result.evaluated_at < sources["attempt"].completed_at:
            raise ValueError("evaluation_timestamp")
        return validate_stored_projection(result, evidence, details=parsed, **sources)


@dataclass(frozen=True)
class ResultHistory:
    attempt: ScenarioAttemptV1
    result: EvaluationResultV1 | None
    error: EvaluationErrorV1 | None = None


class EvaluationService:
    def __init__(self, attempts):
        self.attempts = attempts
        self.accounts = attempts.accounts
        self.publications = attempts.access.publications
        self.scorer = ScoringService()
        self.integrity = StoredEvaluationIntegrityValidation()

    @staticmethod
    def _syntax(attempt_id):
        try:
            return UUID(str(attempt_id))
        except (ValueError, TypeError, AttributeError):
            raise EvaluationFailure("ACCESS_DENIED") from None

    @contextmanager
    def transaction(self, *, write=False, operation="read"):
        try:
            with self.accounts.database.sessions.begin() as db:
                # SQLAlchemy autobegin alone does not start a SQLite read snapshot.
                db.connection().exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
                yield db
        except AccessDenied:
            raise EvaluationFailure("ACCESS_DENIED", operation=operation) from None
        except OperationalError as exc:
            code = (
                "STORAGE_BUSY"
                if "locked" in str(exc.orig).lower()
                else "STORAGE_UNAVAILABLE"
            )
            raise EvaluationFailure(code, operation=operation) from None
        except (IntegrityError, DBAPIError):
            raise EvaluationFailure("STORAGE_FAILURE", operation=operation) from None

    def _owned(self, db, token, aid):
        actor = self.accounts.require(db, token, Role.LEARNER)
        row = db.get(ScenarioAttemptRecord, str(aid))
        if row is None or row.learner_id != actor.id:
            raise AccessDenied()
        return row

    def _sources(self, db, row):
        """Narrow historical loader; invoked only after exact attempt ownership."""
        pub = db.get(ScenarioPublication, row.publication_id)
        if pub is None:
            raise ValueError("missing_publication")
        publication = self.publications._value(pub)
        version = db.get(ScenarioVersion, pub.version_id)
        if version is None or version.status != "published":
            raise ValueError("missing_published_version")
        record = db.get(ScenarioRecord, version.scenario_id)
        state = self.publications.integration._state(
            db, self.publications.scenarios._value(record, version), version
        )
        if not all((state.email, state.web, state.link, state.rubric, state.snapshot)):
            raise ValueError("missing_immutable_source")
        # Availability revision is mutable; all content revisions remain exact.
        expected = publication.manifest.snapshot.model_copy(
            update={"archive_revision": record.archive_revision}
        )
        if state.snapshot != expected:
            raise ValueError("immutable_source_metadata")
        sources = dict(
            manifest=publication.manifest,
            rubric=state.rubric,
            email=state.email,
            web=state.web,
            link=state.link,
            parameters=state.scenario.parameters,
            version_id=state.version_id,
            publication_id=publication.id,
            attempt=attempt_value(row),
        )
        events = tuple(
            event_value(e)
            for e in db.scalars(
                select(AttemptEventRecord)
                .where(AttemptEventRecord.attempt_id == row.id)
                .order_by(AttemptEventRecord.sequence)
            )
        )
        return sources, events

    def _read(self, db, row, *, operation="read"):
        stored = db.scalar(
            select(EvaluationResultRecord).where(
                EvaluationResultRecord.attempt_id == row.id
            )
        )
        if stored is None:
            return None
        try:
            sources, events = self._sources(db, row)
            details = tuple(
                db.scalars(
                    select(EvaluationCriterionRecord)
                    .where(EvaluationCriterionRecord.result_id == stored.id)
                    .order_by(EvaluationCriterionRecord.position)
                )
            )
            return self.integrity.validate(
                stored, details, sources=sources, events=events
            )
        except (ValueError, TypeError, AttributeError, KeyError, ApplicationError):
            raise EvaluationFailure(
                "STORED_EVALUATION_INTEGRITY_ERROR",
                operation=operation,
                attempt_id=safe_uuid(row.id),
                result_id=safe_uuid(stored.id),
                reason="EVIDENCE_BINDING_MISMATCH",
            ) from None

    def read(self, token, attempt_id):
        aid = self._syntax(attempt_id)
        with self.transaction() as db:
            return self._read(db, self._owned(db, token, aid))

    def history(self, token):
        with self.transaction() as db:
            actor = self.accounts.require(db, token, Role.LEARNER)
            rows = db.scalars(
                select(ScenarioAttemptRecord)
                .where(ScenarioAttemptRecord.learner_id == actor.id)
                .order_by(
                    ScenarioAttemptRecord.started_at.desc(), ScenarioAttemptRecord.id
                )
            )
            values = []
            for row in rows:
                try:
                    attempt = attempt_value(row)
                except (ValueError, TypeError, AttributeError, KeyError):
                    # History metadata is an immutable source too. A malformed
                    # attempt cannot be represented as a valid history entry.
                    raise EvaluationFailure(
                        "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
                        attempt_id=safe_uuid(row.id),
                        reason="IMMUTABLE_SOURCE_INVALID",
                    ) from None
                try:
                    result = self._read(db, row)
                    values.append(ResultHistory(attempt, result))
                except EvaluationFailure as exc:
                    values.append(ResultHistory(attempt, None, exc.error))
            return tuple(values)

    def evaluate(self, token, attempt_id):
        aid = self._syntax(attempt_id)
        with self.transaction(write=True, operation="evaluate") as db:
            row = self._owned(db, token, aid)
            if row.status != "COMPLETED":
                raise EvaluationFailure(
                    "ATTEMPT_NOT_COMPLETED", operation="evaluate", attempt_id=aid
                )
            existing = self._read(db, row, operation="evaluate")
            if existing is not None:
                return existing
            try:
                sources, events = self._sources(db, row)
            except (ValueError, TypeError, AttributeError, KeyError, ApplicationError):
                raise EvaluationFailure(
                    "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
                    operation="evaluate",
                    attempt_id=aid,
                    reason="IMMUTABLE_SOURCE_INVALID",
                ) from None
            try:
                evidence = self.scorer.evidence(events=events, **sources)
                result = self.scorer.score(evidence)
                if result.evaluated_at < sources["attempt"].completed_at:
                    raise ValueError("evaluation_timestamp")
            except (ValueError, TypeError, AttributeError, KeyError):
                raise EvaluationFailure(
                    "INVALID_EVIDENCE", operation="evaluate", attempt_id=aid
                ) from None
            # Explicit Core inserts preserve the reviewed detail-first protocol.
            for c in result.criteria:
                db.execute(
                    insert(EvaluationCriterionRecord).values(
                        **criterion_columns(result.result_id, c)
                    )
                )
            db.execute(
                insert(EvaluationResultRecord).values(
                    **result_columns(result, evidence)
                )
            )
            return result
