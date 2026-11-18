"""Versioned local analytics contracts. Session credentials travel separately."""

from datetime import UTC
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from cyberforge.learning.contracts import Status
from cyberforge.scenario_integration.contracts import Digest, Identifier

Count = Annotated[int, Field(strict=True, ge=0)]
Percentage = Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]
PageSize = Annotated[int, Field(strict=True, ge=1, le=100)]
Page = Annotated[int, Field(strict=True, ge=1, le=1_000_000)]
Aggregation = Literal["LATEST_COMPLETED_PER_LEARNER", "ALL_COMPLETED_ATTEMPTS"]
Activity = Literal["NOT_STARTED", "IN_PROGRESS", "ABANDONED", "COMPLETED"]
ResultStatus = Literal[
    "NOT_STARTED",
    "IN_PROGRESS",
    "ABANDONED",
    "COMPLETED_PENDING_EVALUATION",
    "SCORED_ZERO",
    "SCORED_NONZERO",
    "UNSCORABLE",
    "NOT_APPLICABLE",
    "STORED_EVALUATION_INTEGRITY_ERROR",
    "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
]
FeedbackStatus = Literal[
    "VERIFIED", "MISSING_FEEDBACK", "STORED_FEEDBACK_INTEGRITY_ERROR"
]
Outcome = Literal["MET", "NOT_MET", "NOT_APPLICABLE", "DESCRIPTIVE"]
SortKey = Literal["name", "status", "attempts", "score", "last_activity"]


def display_percent(value: Decimal | None) -> str | None:
    return (
        None
        if value is None
        else str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
    )


class AnalyticsValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalyticsQueryV1(AnalyticsValue):
    schema_version: Literal["analytics-query-v1"] = "analytics-query-v1"
    scenario_id: Identifier
    publication_id: Identifier | None = None
    group_id: Identifier | None = None
    started_from: AwareDatetime | None = None
    started_to: AwareDatetime | None = None
    status: Status | None = None
    aggregation: Aggregation = "LATEST_COMPLETED_PER_LEARNER"
    search: str = ""
    sort: SortKey = "name"
    direction: Literal["asc", "desc"] = "asc"
    page: Page = 1
    page_size: PageSize = 25

    @field_validator("search")
    @classmethod
    def normalize_search(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if len(value) > 160 or len(normalized) > 320:
            raise ValueError("search length")
        return normalized

    @field_validator("started_from", "started_to")
    @classmethod
    def utc_bound(cls, value):
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def ordered_bounds(self) -> Self:
        if (
            self.started_from
            and self.started_to
            and self.started_from >= self.started_to
        ):
            raise ValueError("invalid period")
        return self


class HistoryQueryV1(AnalyticsValue):
    schema_version: Literal["analytics-history-query-v1"] = "analytics-history-query-v1"
    learner_id: Identifier
    attempt_id: UUID | None = None
    result_id: UUID | None = None
    page: Page = 1
    page_size: PageSize = 25

    @model_validator(mode="after")
    def bind_result(self) -> Self:
        if self.result_id is not None and self.attempt_id is None:
            raise ValueError("result requires attempt")
        return self


class GroupOption(AnalyticsValue):
    id: Identifier
    name: str = Field(min_length=1, max_length=120)


class PublicationOption(AnalyticsValue):
    id: Identifier
    version: Identifier
    published_at: AwareDatetime


class AnalyticsScope(AnalyticsValue):
    name: str = Field(min_length=1, max_length=200)
    topic: str = Field(max_length=2000)
    difficulty: str = Field(max_length=100)
    audience: str = Field(max_length=1000)
    created_at: AwareDatetime
    status: Literal["draft", "published", "archived"]
    publications: tuple[PublicationOption, ...] = Field(max_length=100_000)
    groups: tuple[GroupOption, ...] = Field(max_length=100_000)


class Ratio(AnalyticsValue):
    numerator: Count
    denominator: Count

    @model_validator(mode="after")
    def valid_counts(self) -> Self:
        if self.numerator > self.denominator:
            raise ValueError("numerator exceeds denominator")
        return self

    @property
    def percent(self) -> Decimal | None:
        if self.denominator:
            with localcontext(prec=40, rounding=ROUND_HALF_EVEN):
                return Decimal(100 * self.numerator) / Decimal(self.denominator)
        return None


class CriterionKey(AnalyticsValue):
    publication_id: Identifier
    scenario_version: Identifier
    rubric_revision: Identifier
    rubric_digest: Digest
    scoring_strategy: str = Field(min_length=1, max_length=50)
    criterion_id: str = Field(min_length=1, max_length=40)


class CriterionStatisticsV1(AnalyticsValue):
    key: CriterionKey
    position: Count
    label: str = Field(min_length=1, max_length=200)
    phase: Literal["email", "transition", "web"]
    met: Count
    not_met: Count
    not_applicable: Count
    descriptive: Count
    verified: Count

    @model_validator(mode="after")
    def covered(self) -> Self:
        if (
            self.met + self.not_met + self.not_applicable + self.descriptive
            > self.verified
        ):
            raise ValueError("criterion exceeds coverage")
        return self

    @property
    def met_rate(self) -> Ratio:
        return Ratio(numerator=self.met, denominator=self.met + self.not_met)

    @property
    def not_met_rate(self) -> Ratio:
        return Ratio(numerator=self.not_met, denominator=self.met + self.not_met)


class EvaluationCoverage(AnalyticsValue):
    scored_zero: Count = 0
    scored_nonzero: Count = 0
    unscorable: Count = 0
    pending: Count = 0
    stored_integrity_error: Count = 0
    source_integrity_error: Count = 0
    feedback_missing: Count = 0
    feedback_integrity_error: Count = 0

    @property
    def scored(self) -> int:
        return self.scored_zero + self.scored_nonzero

    @property
    def verified(self) -> int:
        return self.scored + self.unscorable

    @property
    def total(self) -> int:
        return (
            self.verified
            + self.pending
            + self.stored_integrity_error
            + self.source_integrity_error
        )

    @model_validator(mode="after")
    def covered_feedback(self) -> Self:
        if self.feedback_missing + self.feedback_integrity_error > self.verified:
            raise ValueError("feedback exceeds verified results")
        return self


class AnalyticsDataQualityV1(AnalyticsValue):
    schema_version: Literal["analytics-data-quality-v1"] = "analytics-data-quality-v1"
    availability: Literal["AVAILABLE"] = "AVAILABLE"
    filtered: EvaluationCoverage
    selected: EvaluationCoverage
    # Latest mode can suppress a learner's numerical result when ordering is unreliable.
    ordering_errors: Count = 0

    @model_validator(mode="after")
    def valid_coverage(self) -> Self:
        if self.ordering_errors > self.filtered.source_integrity_error or any(
            getattr(self.selected, field) > getattr(self.filtered, field)
            for field in EvaluationCoverage.model_fields
        ):
            raise ValueError("selected coverage exceeds filtered coverage")
        return self


class LifecycleCounts(AnalyticsValue):
    in_progress: Count = 0
    abandoned: Count = 0
    completed: Count = 0

    @property
    def total(self) -> int:
        return self.in_progress + self.abandoned + self.completed


class Observations(AnalyticsValue):
    confirm: Count = 0
    submit_synthetic: Count = 0
    critical_policy: Literal["NOT_CONFIGURED"] = "NOT_CONFIGURED"
    critical_count: None = None


class ScenarioMetricsV1(AnalyticsValue):
    schema_version: Literal["scenario-metrics-v1"] = "scenario-metrics-v1"
    current_learners: Count
    participating_learners: Count
    completing_learners: Count
    lifecycle: LifecycleCounts
    mean_score: Percentage | None
    scored_coverage: Ratio
    score_distribution: tuple[Count, Count, Count, Count, Count]
    scored_versions: Count
    web_transition: Ratio
    observations: Observations

    @model_validator(mode="after")
    def valid_coverage(self) -> Self:
        if (
            self.completing_learners > self.participating_learners
            or self.participating_learners > self.lifecycle.total
            or self.completing_learners > self.lifecycle.completed
            or sum(self.score_distribution) != self.scored_coverage.numerator
            or (self.mean_score is None) != (self.scored_coverage.numerator == 0)
            or not self.scored_versions
            <= self.scored_coverage.numerator
            <= self.web_transition.denominator
            <= self.scored_coverage.denominator
            <= self.lifecycle.completed
        ):
            raise ValueError("inconsistent metric coverage")
        return self


class CriterionSummary(AnalyticsValue):
    met: Count = 0
    not_met: Count = 0
    not_applicable: Count = 0
    descriptive: Count = 0


class LearnerAnalyticsRowV1(AnalyticsValue):
    schema_version: Literal["learner-analytics-row-v1"] = "learner-analytics-row-v1"
    learner_id: Identifier
    name: str = Field(min_length=1, max_length=160)
    username: str = Field(min_length=1, max_length=80)
    groups: tuple[GroupOption, ...] = Field(max_length=100_000)
    current: bool
    historical: bool
    activity: Activity
    attempts: LifecycleCounts
    last_activity: AwareDatetime | None
    score: Percentage | None
    result_status: ResultStatus
    coverage: EvaluationCoverage
    email: CriterionSummary | None
    web: CriterionSummary | None
    web_not_applicable: bool
    observations: Observations

    @model_validator(mode="after")
    def valid_cohort(self) -> Self:
        if (
            self.historical != bool(self.attempts.total)
            or (self.activity == "NOT_STARTED") != (self.last_activity is None)
            or (not self.current and not self.historical)
            or self.coverage.total > self.attempts.completed
            or (self.score is None) != (self.coverage.scored == 0)
        ):
            raise ValueError("inconsistent learner projection")
        return self


class CriterionDetail(AnalyticsValue):
    key: CriterionKey
    label: str = Field(min_length=1, max_length=200)
    phase: Literal["email", "transition", "web"]
    position: Count
    outcome: Outcome


class AttemptAnalyticsDetailV1(AnalyticsValue):
    schema_version: Literal["attempt-analytics-detail-v1"] = (
        "attempt-analytics-detail-v1"
    )
    learner_id: Identifier
    attempt_id: UUID
    scenario_id: Identifier
    publication: PublicationOption
    group: GroupOption
    activity: Status
    started_at: AwareDatetime
    completed_at: AwareDatetime | None
    last_activity: AwareDatetime
    result_id: UUID | None
    result_status: ResultStatus
    score: Percentage | None
    unscorable_reason: Literal["NO_APPLICABLE_NUMERICAL_CRITERIA"] | None = None
    rubric_revision: Identifier | None = None
    rubric_digest: Digest | None = None
    scoring_strategy: str | None = Field(default=None, max_length=50)
    criteria: tuple[CriterionDetail, ...] = Field(max_length=128)
    web_entered: bool | None
    web_not_applicable: bool
    facts: tuple[Annotated[str, Field(max_length=1000)], ...] = Field(max_length=30)
    observations: Observations
    feedback_status: FeedbackStatus | None
    feedback: tuple[Annotated[str, Field(max_length=1000)], ...] = Field(max_length=48)


class LearnerAnalyticsHistory(AnalyticsValue):
    captured_at: AwareDatetime
    learner_id: Identifier
    name: str = Field(min_length=1, max_length=160)
    username: str = Field(min_length=1, max_length=80)
    total: Count
    attempts: tuple[AttemptAnalyticsDetailV1, ...] = Field(max_length=100)


class ScenarioAnalyticsSnapshotV1(AnalyticsValue):
    schema_version: Literal["scenario-analytics-snapshot-v1"] = (
        "scenario-analytics-snapshot-v1"
    )
    query: AnalyticsQueryV1
    captured_at: AwareDatetime
    scope: AnalyticsScope
    metrics: ScenarioMetricsV1
    criteria: tuple[CriterionStatisticsV1, ...] = Field(max_length=100_000)
    quality: AnalyticsDataQualityV1
    total_learners: Count
    rows: tuple[LearnerAnalyticsRowV1, ...] = Field(max_length=100)
    recommendations: tuple[Annotated[str, Field(max_length=1000)], ...] = Field(
        max_length=12
    )

    @model_validator(mode="after")
    def coherent_snapshot(self) -> Self:
        if (
            len(self.rows) > min(self.query.page_size, self.total_learners)
            or self.metrics.lifecycle.completed != self.quality.filtered.total
            or self.metrics.scored_coverage.denominator != self.quality.selected.total
            or self.metrics.scored_coverage.numerator != self.quality.selected.scored
            or self.metrics.web_transition.denominator != self.quality.selected.verified
        ):
            raise ValueError("inconsistent snapshot coverage")
        return self


class AnalyticsExportManifestV1(AnalyticsValue):
    schema_version: Literal["analytics-export-manifest-v1"] = (
        "analytics-export-manifest-v1"
    )
    captured_at: AwareDatetime
    scenario_id: Identifier
    publication_id: Identifier | None
    group_id: Identifier | None
    publications: tuple[Identifier, ...] = Field(max_length=100_000)
    groups: tuple[Identifier, ...] = Field(max_length=100_000)
    started_from: AwareDatetime | None
    started_to: AwareDatetime | None
    status: Status | None
    aggregation: Aggregation
    search_applied: bool
    sort: SortKey
    direction: Literal["asc", "desc"]
    row_count: Count
    score_unit: Literal["percent"] = "percent"
    missing_score: Literal["null_json_empty_csv_with_status"] = (
        "null_json_empty_csv_with_status"
    )
    metrics: ScenarioMetricsV1
    criteria: tuple[CriterionStatisticsV1, ...] = Field(max_length=100_000)
    quality: AnalyticsDataQualityV1
