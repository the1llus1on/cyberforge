"""D12-10 wire contracts and pure projection over verified Analytics sources."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cyberforge.analytics.contracts import AttemptAnalyticsDetailV1
from cyberforge.analytics.recommendations import TOPIC_BY_CRITERION

Topic = Literal[
    "data_protection", "link_inspection", "reporting", "sender_verification"
]
RecommendationId = Literal[
    "protect_credentials",
    "practice_data_minimization",
    "check_destination",
    "use_known_address",
    "use_reporting_channel",
    "practice_reporting",
    "verify_sender_independently",
    "check_sender_address",
]
RECOMMENDATION_CATALOG = MappingProxyType(
    {
        "protect_credentials": (
            "data_protection",
            "Відпрацюйте відмову від введення справжніх облікових даних "
            "у навчальні форми чи на підозрілих сторінках.",
        ),
        "practice_data_minimization": (
            "data_protection",
            "Обговоріть, як перевірити необхідність запиту конфіденційних даних.",
        ),
        "check_destination": (
            "link_inspection",
            "Відпрацюйте перевірку адреси призначення перед переходом за посиланням.",
        ),
        "use_known_address": (
            "link_inspection",
            "Покажіть, як відкрити потрібний ресурс за відомою довіреною адресою.",
        ),
        "use_reporting_channel": (
            "reporting",
            "Повторіть порядок повідомлення про підозріле звернення "
            "через затверджений канал.",
        ),
        "practice_reporting": (
            "reporting",
            "Проведіть вправу з повідомлення про підозріле звернення "
            "без пересилання конфіденційних даних.",
        ),
        "verify_sender_independently": (
            "sender_verification",
            "Відпрацюйте перевірку відправника через незалежний довірений канал.",
        ),
        "check_sender_address": (
            "sender_verification",
            "Запропонуйте порівняти відображуване ім’я з повною адресою відправника.",
        ),
    }
)
TOPIC_INSTRUCTIONS = (
    "Select and order one to four recommendation IDs for the supplied topics. "
    "Use each topic at most once. Return only the response schema. "
    "Allowed choices: data_protection (protect_credentials, "
    "practice_data_minimization); link_inspection (check_destination, "
    "use_known_address); reporting (use_reporting_channel, practice_reporting); "
    "sender_verification (verify_sender_independently, check_sender_address)."
)


class _TopicContract(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


class AssistantTopicInputV1(_TopicContract):
    schema_version: Literal["assistant-topic-input-v1"]
    topics: tuple[Topic, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def canonical_topics(self) -> Self:
        if tuple(sorted(set(self.topics))) != self.topics:
            raise ValueError("noncanonical_topics")
        return self

    def payload(self) -> str:
        return self.model_dump_json()


class TopicRecommendationV1(_TopicContract):
    topic: Topic
    recommendation_id: RecommendationId

    @model_validator(mode="after")
    def compatible_choice(self) -> Self:
        if RECOMMENDATION_CATALOG[self.recommendation_id][0] != self.topic:
            raise ValueError("incompatible_recommendation")
        return self


class AssistantTopicSelectionV1(_TopicContract):
    schema_version: Literal["assistant-topic-selection-v1"]
    recommendations: tuple[TopicRecommendationV1, ...] = Field(
        min_length=1, max_length=4
    )

    @model_validator(mode="after")
    def unique_topics(self) -> Self:
        if len({choice.topic for choice in self.recommendations}) != len(
            self.recommendations
        ):
            raise ValueError("duplicate_recommendation_topic")
        return self


def selection_schema() -> str:
    return json.dumps(
        AssistantTopicSelectionV1.model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True, repr=False)
class TopicWireRequestV1:
    payload: str
    instructions: str
    response_schema: str

    @classmethod
    def from_input(cls, request: AssistantTopicInputV1) -> Self:
        payload = request.payload()
        checked = AssistantTopicInputV1.model_validate_json(payload)
        return cls(checked.payload(), TOPIC_INSTRUCTIONS, selection_schema())

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            [self.payload, self.instructions, self.response_schema],
            separators=(",", ":"),
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


def decode_selection(raw: str, request: AssistantTopicInputV1) -> tuple[str, ...]:
    """Validate the complete reply before rendering approved local text."""
    if len(raw) > 4096:
        raise ValueError("oversize_topic_selection")
    json.loads(raw, object_pairs_hook=_unique_object)
    answer = AssistantTopicSelectionV1.model_validate_json(raw)
    if any(choice.topic not in request.topics for choice in answer.recommendations):
        raise ValueError("unrequested_recommendation_topic")
    return tuple(
        RECOMMENDATION_CATALOG[choice.recommendation_id][1]
        for choice in answer.recommendations
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate_selection_field")
    return result


def project_topics(
    selected: Iterable[AttemptAnalyticsDetailV1],
    *,
    ordering_error: bool,
) -> AssistantTopicInputV1 | None:
    """Use only the trusted A11 reader's already-selected completed results."""
    if ordering_error:
        return None
    attempts = tuple(selected)
    publications = {attempt.publication.id for attempt in attempts}
    if len(publications) != 1 or any(
        attempt.activity != "COMPLETED"
        or attempt.result_status
        in {
            "STORED_EVALUATION_INTEGRITY_ERROR",
            "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
        }
        for attempt in attempts
    ):
        return None
    scored = tuple(
        attempt
        for attempt in attempts
        if attempt.result_status in {"SCORED_ZERO", "SCORED_NONZERO"}
    )
    rubric_keys = {
        (attempt.rubric_revision, attempt.rubric_digest, attempt.scoring_strategy)
        for attempt in scored
    }
    if len(rubric_keys) != 1 or any(
        attempt.result_id is None
        or attempt.score is None
        or not attempt.criteria
        or None
        in (attempt.rubric_revision, attempt.rubric_digest, attempt.scoring_strategy)
        for attempt in scored
    ):
        return None
    criteria = tuple(criterion for attempt in scored for criterion in attempt.criteria)
    target = "NOT_MET" if any(c.outcome == "NOT_MET" for c in criteria) else "MET"
    topics = sorted(
        {
            TOPIC_BY_CRITERION[criterion.key.criterion_id]
            for criterion in criteria
            if criterion.outcome == target
            and criterion.key.criterion_id in TOPIC_BY_CRITERION
        }
    )
    if not topics:
        return None
    return AssistantTopicInputV1.model_validate(
        {"schema_version": "assistant-topic-input-v1", "topics": tuple(topics)}
    )


def offline_recommendations(
    request: AssistantTopicInputV1 | None,
) -> tuple[str, ...]:
    if request is None:
        return (
            "Повторіть з учнями перевірку відправника й посилань та порядок "
            "повідомлення про підозрілі звернення.",
        )
    first_by_topic = {}
    for topic, text in RECOMMENDATION_CATALOG.values():
        first_by_topic.setdefault(topic, text)
    return tuple(first_by_topic[topic] for topic in request.topics)
