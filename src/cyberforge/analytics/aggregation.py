"""Deterministic aggregation over verified, authorized attempt projections."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext

from cyberforge.analytics.contracts import (
    AnalyticsDataQualityV1,
    AnalyticsQueryV1,
    CriterionStatisticsV1,
    CriterionSummary,
    EvaluationCoverage,
    GroupOption,
    LearnerAnalyticsRowV1,
    LifecycleCounts,
    Observations,
    Ratio,
    ScenarioMetricsV1,
)

STATUS_ORDER = ("NOT_STARTED", "IN_PROGRESS", "ABANDONED", "COMPLETED")
RESULT_FIELDS = {
    "SCORED_ZERO": "scored_zero",
    "SCORED_NONZERO": "scored_nonzero",
    "UNSCORABLE": "unscorable",
    "COMPLETED_PENDING_EVALUATION": "pending",
    "STORED_EVALUATION_INTEGRITY_ERROR": "stored_integrity_error",
    "IMMUTABLE_SOURCE_INTEGRITY_ERROR": "source_integrity_error",
}
EMPTY_TIME = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Learner:
    id: int
    name: str
    username: str


def _lifecycle(attempts):
    counts = Counter(a.detail.activity for a in attempts)
    return LifecycleCounts(**{key.lower(): value for key, value in counts.items()})


def _coverage(attempts):
    counts = Counter(RESULT_FIELDS[a.detail.result_status] for a in attempts)
    counts.update(
        {
            "feedback_missing": sum(
                a.detail.feedback_status == "MISSING_FEEDBACK" for a in attempts
            ),
            "feedback_integrity_error": sum(
                a.detail.feedback_status == "STORED_FEEDBACK_INTEGRITY_ERROR"
                for a in attempts
            ),
        }
    )
    return EvaluationCoverage(**counts)


def _mean(values):
    if not values:
        return None
    with localcontext(prec=40):
        return sum(values, Decimal(0)) / len(values)


def _observations(attempts):
    return Observations(
        confirm=sum(a.detail.observations.confirm for a in attempts),
        submit_synthetic=sum(a.detail.observations.submit_synthetic for a in attempts),
    )


def _phase(attempts, phase):
    counts = Counter(
        c.outcome.lower()
        for a in attempts
        for c in a.detail.criteria
        if c.phase == phase
    )
    return CriterionSummary(**counts) if counts else None


def _select(completed, mode):
    if mode == "ALL_COMPLETED_ATTEMPTS":
        return completed
    # Ordering ambiguity must never turn an earlier verified result into latest.
    errors = [a for a in completed if a.ordering_error]
    if errors:
        return [min(errors, key=lambda a: a.detail.attempt_id)]
    if not completed:
        return []
    return [
        max(
            sorted(completed, key=lambda a: a.detail.attempt_id),
            key=lambda a: a.detail.completed_at or EMPTY_TIME,
        )
    ]


def _row(learner, groups, current, attempts, selected):
    scores = [a.detail.score for a in selected if a.detail.score is not None]
    score = _mean(scores)
    latest = None
    if attempts:
        latest = max(
            sorted(attempts, key=lambda a: (a.detail.attempt_id, -a.activity_sequence)),
            key=lambda a: a.detail.last_activity,
        ).detail
    coverage = _coverage(selected)
    if score is not None:
        state = "SCORED_NONZERO" if score else "SCORED_ZERO"
    elif selected:
        # In all-completed mode coverage retains all distinct reasons.
        state = next(
            status
            for status in (
                "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
                "STORED_EVALUATION_INTEGRITY_ERROR",
                "COMPLETED_PENDING_EVALUATION",
                "UNSCORABLE",
            )
            if any(a.detail.result_status == status for a in selected)
        )
    else:
        state = latest.result_status if latest else "NOT_STARTED"
    web = _phase(selected, "web")
    verified = [a.detail for a in selected if a.detail.result_id is not None]
    return LearnerAnalyticsRowV1(
        learner_id=learner.id,
        name=learner.name,
        username=learner.username,
        groups=tuple(
            GroupOption(id=gid, name=groups[gid])
            for gid in sorted(set(current) | {a.detail.group.id for a in attempts})
        ),
        current=bool(current),
        historical=bool(attempts),
        activity=latest.activity if latest else "NOT_STARTED",
        attempts=_lifecycle(attempts),
        last_activity=latest.last_activity if latest else None,
        score=score,
        result_status=state,
        coverage=coverage,
        email=_phase(selected, "email"),
        web=web,
        web_not_applicable=bool(verified)
        and all(a.web_not_applicable for a in verified),
        observations=_observations(selected),
    )


def _criteria(verified):
    compatible = Counter()
    counts = defaultdict(Counter)
    metadata = {}
    for attempt in verified:
        for criterion in attempt.detail.criteria:
            metadata[criterion.key] = criterion
            counts[criterion.key][criterion.outcome.lower()] += 1
        compatible[_compatibility(attempt.detail.criteria[0].key)] += 1

    ordered = sorted(
        metadata.values(),
        key=lambda criterion: (
            criterion.key.scenario_version,
            *_compatibility(criterion.key),
            criterion.position,
            criterion.key.criterion_id,
        ),
    )
    return tuple(
        CriterionStatisticsV1(
            key=criterion.key,
            position=criterion.position,
            label=criterion.label,
            phase=criterion.phase,
            met=counts[criterion.key]["met"],
            not_met=counts[criterion.key]["not_met"],
            not_applicable=counts[criterion.key]["not_applicable"],
            descriptive=counts[criterion.key]["descriptive"],
            verified=compatible[_compatibility(criterion.key)],
        )
        for criterion in ordered
    )


def _compatibility(key):
    return (
        key.publication_id,
        key.rubric_revision,
        key.rubric_digest,
        key.scoring_strategy,
    )


def _sort(rows, query):
    key = {
        "name": lambda row: row.name.casefold(),
        "status": lambda row: STATUS_ORDER.index(row.activity),
        "attempts": lambda row: row.attempts.total,
        "score": lambda row: row.score,
        "last_activity": lambda row: row.last_activity,
    }[query.sort]
    rows.sort(key=lambda row: row.learner_id)
    present = [row for row in rows if key(row) is not None]
    present.sort(key=key, reverse=query.direction == "desc")
    return tuple(present + [row for row in rows if key(row) is None])


def aggregate(query: AnalyticsQueryV1, learners, groups, current, attempts):
    by_learner = defaultdict(list)
    for attempt in attempts:
        by_learner[attempt.detail.learner_id].append(attempt)
    all_completed, selected, rows = [], [], []
    for learner_id in current.keys() | by_learner.keys():
        history = by_learner.get(learner_id, ())
        completed = [a for a in history if a.detail.activity == "COMPLETED"]
        selection = _select(completed, query.aggregation)
        all_completed.extend(completed)
        selected.extend(selection)
        rows.append(
            _row(
                learners[learner_id],
                groups,
                current.get(learner_id, ()),
                history,
                selection,
            )
        )
    verified = [a for a in selected if a.detail.result_id is not None]
    scores = [a.detail.score for a in verified if a.detail.score is not None]
    bins = [0] * 5
    for score in scores:
        bins[min(int(score // 20), 4)] += 1
    metrics = ScenarioMetricsV1(
        current_learners=len(current),
        participating_learners=len(by_learner),
        completing_learners=len({a.detail.learner_id for a in all_completed}),
        lifecycle=_lifecycle(attempts),
        mean_score=_mean(scores),
        scored_coverage=Ratio(numerator=len(scores), denominator=len(selected)),
        score_distribution=tuple(bins),
        scored_versions=len(
            {a.detail.publication.id for a in verified if a.detail.score is not None}
        ),
        web_transition=Ratio(
            numerator=sum(a.detail.web_entered is True for a in verified),
            denominator=len(verified),
        ),
        observations=_observations(verified),
    )
    quality = AnalyticsDataQualityV1(
        filtered=_coverage(all_completed),
        selected=_coverage(selected),
        ordering_errors=sum(a.ordering_error for a in all_completed),
    )
    return metrics, quality, _criteria(verified), _sort(rows, query)
