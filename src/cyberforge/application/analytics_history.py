"""Internal batched reader for already-authorized historical attempt rows."""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import String, cast, select
from sqlalchemy.orm import defer

from cyberforge.analytics.contracts import (
    AttemptAnalyticsDetailV1,
    CriterionDetail,
    CriterionKey,
    GroupOption,
    Observations,
    PublicationOption,
)
from cyberforge.application.evaluations import EvaluationFailure, safe_uuid
from cyberforge.application.learner_attempts import attempt_value, event_value
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.domain.accounts import ApplicationError
from cyberforge.evaluation.facts import project_facts
from cyberforge.evaluation.validation import replay
from cyberforge.learning.contracts import utc
from cyberforge.persistence.models import (
    AttemptEventRecord,
    EvaluationCriterionRecord,
    EvaluationResultRecord,
    MentorFeedbackRecord,
)

INVALID = (
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
    ApplicationError,
)
BATCH_SIZE = 200


@dataclass(frozen=True)
class HistoricalAttempt:
    detail: AttemptAnalyticsDetailV1
    ordering_error: bool
    activity_sequence: int


def _parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is None else None
    except ValueError:
        return None


def attempt_with_times(row, started, completed, abandoned):
    return SimpleNamespace(
        **row.__dict__,
        started_at=_parse_time(started),
        completed_at=_parse_time(completed),
        abandoned_at=_parse_time(abandoned),
    )


def _agrees_on_historical_attribution(row, stored):
    if stored is None:
        return True
    # Canonical attempt identities can corroborate attribution despite a
    # damaged evaluation projection. The stored-result validator checks that
    # projection separately.
    corroborated = False
    for document in (stored.result_json, stored.evidence_json):
        try:
            persisted = json.loads(document)["attempt"]
            identity = tuple(
                persisted[k]
                for k in (
                    "attempt_id",
                    "scenario_id",
                    "publication_id",
                    "learner_id",
                    "authorization_group_id",
                )
            )
        except (ValueError, KeyError, TypeError):
            continue
        if identity != (
            row.id,
            row.scenario_id,
            row.publication_id,
            row.learner_id,
            row.authorization_group_id,
        ):
            return False
        corroborated = True
    # When both copies of the identity are unreadable, preserve the existing
    # fail-closed behavior for conflicting attribution.
    return corroborated or (
        stored.scenario_id,
        stored.learner_id,
        stored.publication_id,
    ) == (
        row.scenario_id,
        row.learner_id,
        row.publication_id,
    )


class _HistoricalReader:
    def __init__(self, evaluations, db, publications, groups, *, include_details):
        self.evaluations = evaluations
        self.db = db
        self.publications = publications
        self.groups = groups
        self.include_details = include_details
        self.sources = {}

    def read_batch(self, rows):
        ids = [row.id for row in rows]
        results = {
            r.attempt_id: r
            for r in self.db.scalars(
                select(EvaluationResultRecord).where(
                    EvaluationResultRecord.attempt_id.in_(ids)
                )
            )
        }
        result_ids = [result.id for result in results.values()]
        detail_rows = defaultdict(list)
        for row in self.db.scalars(
            select(EvaluationCriterionRecord)
            .where(EvaluationCriterionRecord.result_id.in_(result_ids))
            .order_by(EvaluationCriterionRecord.position)
        ):
            detail_rows[row.result_id].append(row)
        feedback = {
            row.result_id: row
            for row in self.db.scalars(
                select(MentorFeedbackRecord).where(
                    MentorFeedbackRecord.result_id.in_(result_ids)
                )
            )
        }
        events = defaultdict(list)
        for row, timestamp in self.db.execute(
            select(AttemptEventRecord, cast(AttemptEventRecord.timestamp, String))
            .options(defer(AttemptEventRecord.timestamp))
            .where(AttemptEventRecord.attempt_id.in_(ids))
            .order_by(AttemptEventRecord.sequence)
        ):
            events[row.attempt_id].append(
                SimpleNamespace(**row.__dict__, timestamp=_parse_time(timestamp))
            )
        for row in rows:
            stored = results.get(row.id)
            if not _agrees_on_historical_attribution(row, stored):
                continue
            result_id = stored.id if stored is not None else None
            value = self._project(
                row,
                stored,
                detail_rows.get(result_id, ()),
                feedback.get(result_id),
                events.get(row.id, ()),
            )
            if value is not None:
                yield value

    def _sources(self, publication):
        if publication.id not in self.sources:
            try:
                self.sources[publication.id] = self.evaluations._publication_sources(
                    self.db, publication
                )
            except INVALID:
                self.sources[publication.id] = None
        return self.sources[publication.id]

    def _project(self, row, stored, details, feedback_row, event_rows):
        attempt_id = safe_uuid(row.id)
        if (
            attempt_id is None
            or str(attempt_id) != row.id
            or row.started_at is None
            or row.status not in {"COMPLETED", "IN_PROGRESS", "ABANDONED"}
        ):
            return None
        publication, version = self.publications[row.publication_id]
        group = self.groups[row.authorization_group_id]
        started = utc(row.started_at)
        completed = utc(row.completed_at)
        terminal = event_rows[-1] if event_rows else None
        ordering_error = row.status == "COMPLETED" and (
            completed is None
            or completed < started
            or terminal is None
            or terminal.surface != "system"
            or terminal.action_id != "completed"
            or terminal.timestamp != row.completed_at
        )
        last_activity, sequence = started, 0
        state = row.status
        result = feedback = None
        feedback_status = None
        try:
            attempt = attempt_value(row)
            events = tuple(event_value(event) for event in event_rows)
            if len(events) != attempt.last_event_sequence or any(
                e.attempt_id != attempt_id or e.sequence != i or e.timestamp < started
                for i, e in enumerate(events, 1)
            ):
                raise ValueError("event_binding")
            latest = max(events, key=lambda e: (e.timestamp, e.sequence), default=None)
            if latest is not None:
                last_activity, sequence = latest.timestamp, latest.sequence
            if row.status == "COMPLETED":
                sources = self._sources(publication)
                if (
                    sources is None
                    or attempt.scenario_version != version.number
                    or attempt.manifest_digest != publication.manifest_digest
                ):
                    raise ValueError("attempt_source")
                if stored is None:
                    replay(attempt, events)
                    state = "COMPLETED_PENDING_EVALUATION"
                else:
                    result = self.evaluations.integrity.validate(
                        stored,
                        details,
                        sources=dict(sources, attempt=attempt),
                        events=events,
                    )
        except INVALID:
            state = (
                "STORED_EVALUATION_INTEGRITY_ERROR"
                if stored is not None
                else "IMMUTABLE_SOURCE_INTEGRITY_ERROR"
            )
            if ordering_error:
                state = "IMMUTABLE_SOURCE_INTEGRITY_ERROR"

        criteria = facts = feedback_text = ()
        web_entered = None
        web_not_applicable = False
        observations = Observations()
        score = result_id = None
        if result is not None:
            score = result.score_percent
            result_id = result.result_id
            state = (
                "UNSCORABLE"
                if score is None
                else "SCORED_NONZERO"
                if score
                else "SCORED_ZERO"
            )
            criteria = tuple(
                CriterionDetail(
                    key=CriterionKey(
                        publication_id=publication.id,
                        scenario_version=version.number,
                        rubric_revision=result.source.snapshot.rubric_revision,
                        rubric_digest=result.source.snapshot.rubric_digest,
                        scoring_strategy=result.scoring_strategy,
                        criterion_id=c.criterion.criterion_id,
                    ),
                    label=c.criterion.label,
                    phase=c.criterion.phase,
                    position=c.position,
                    outcome=c.outcome,
                )
                for c in result.criteria
            )
            web_entered = any(
                e.surface == "system" and e.action_id == "web_entered" for e in events
            )
            web_not_applicable = result.path.kind == "SAFE_DECLINE"
            if self.include_details:
                facts = tuple(f.observation for f in project_facts(result)[0])
            observations = Observations(
                confirm=sum(
                    o.action_id == "confirm" for o in result.critical_observations
                ),
                submit_synthetic=sum(
                    o.action_id == "submit_synthetic"
                    for o in result.critical_observations
                ),
            )
            try:
                feedback = MentorFeedbackService._validate_row(feedback_row, result)
                feedback_status = "VERIFIED" if feedback else "MISSING_FEEDBACK"
            except EvaluationFailure:
                feedback_status = "STORED_FEEDBACK_INTEGRITY_ERROR"
            if self.include_details and feedback is not None:
                explanation = feedback.explanation
                feedback_text = (
                    *(f.explanation for f in explanation.selected_facts),
                    *explanation.recommendations,
                    *explanation.limitations,
                )
        return HistoricalAttempt(
            AttemptAnalyticsDetailV1(
                learner_id=row.learner_id,
                attempt_id=attempt_id,
                scenario_id=row.scenario_id,
                publication=PublicationOption(
                    id=publication.id,
                    version=version.number,
                    published_at=utc(publication.published_at),
                ),
                group=GroupOption(id=group.id, name=group.name),
                activity=row.status,
                started_at=started,
                completed_at=completed if not ordering_error else None,
                last_activity=last_activity,
                result_id=result_id,
                result_status=state,
                score=score,
                unscorable_reason=result.reason_code if result else None,
                rubric_revision=result.source.snapshot.rubric_revision
                if result
                else None,
                rubric_digest=result.source.snapshot.rubric_digest if result else None,
                scoring_strategy=result.scoring_strategy if result else None,
                criteria=criteria,
                web_entered=web_entered,
                web_not_applicable=web_not_applicable,
                facts=facts,
                observations=observations,
                feedback_status=feedback_status,
                feedback=feedback_text,
            ),
            ordering_error,
            sequence,
        )
