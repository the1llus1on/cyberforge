import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import get_args
from uuid import UUID

import pytest
from pydantic import ValidationError

from cyberforge.analytics.advisory_authorization import (
    AdvisoryPolicyEvidenceV1,
    AdvisoryPreviewBinding,
    ProviderPrivacyProfileV1,
)
from cyberforge.analytics.aggregation import _select
from cyberforge.analytics.contracts import AttemptAnalyticsDetailV1
from cyberforge.analytics.recommendations import TOPIC_BY_CRITERION
from cyberforge.analytics.topic_advisory import (
    RECOMMENDATION_CATALOG,
    TOPIC_INSTRUCTIONS,
    AssistantTopicInputV1,
    RecommendationId,
    Topic,
    TopicWireRequestV1,
    decode_selection,
    offline_recommendations,
    project_topics,
)
from cyberforge.application.analytics_history import HistoricalAttempt

NOW = datetime(2026, 11, 18, tzinfo=UTC)
PAYLOAD = (
    '{"schema_version":"assistant-topic-input-v1",'
    '"topics":["link_inspection","sender_verification"]}'
)
WIRE_DIGEST = "a538acc8a598dceeea770d7dc550a04d51c40cba6595783559b22da3009333d8"


def scored(*criteria, learner=10, publication=20, score=0):
    rubric = {
        "rubric_revision": 1,
        "rubric_digest": "a" * 64,
        "scoring_strategy": "weighted-v1",
    }
    return AttemptAnalyticsDetailV1.model_validate(
        {
            "learner_id": learner,
            "attempt_id": UUID(int=learner),
            "scenario_id": 30,
            "publication": {"id": publication, "version": 1, "published_at": NOW},
            "group": {"id": 40, "name": "Навчальна група"},
            "activity": "COMPLETED",
            "started_at": NOW,
            "completed_at": NOW,
            "last_activity": NOW,
            "result_id": UUID(int=learner + 100),
            "result_status": "SCORED_NONZERO" if score else "SCORED_ZERO",
            "score": score,
            **rubric,
            "criteria": [
                {
                    "key": {
                        "publication_id": publication,
                        "scenario_version": 1,
                        "criterion_id": criterion,
                        **rubric,
                    },
                    "label": "Критерій",
                    "phase": "email",
                    "position": index,
                    "outcome": outcome,
                }
                for index, (criterion, outcome) in enumerate(criteria)
            ],
            "web_entered": False,
            "web_not_applicable": True,
            "facts": (),
            "observations": {},
            "feedback_status": None,
            "feedback": (),
        }
    )


def test_projection_and_wire_equality_across_cohorts_and_outcomes():
    practice = scored(
        ("email.sender", "NOT_MET"),
        ("email.link", "NOT_MET"),
        ("email.report", "MET"),
        ("web.address", "NOT_APPLICABLE"),
        score=33,
    )
    reinforce = scored(("email.link", "MET"), ("email.sender", "MET"), score=100)
    zero = scored(("email.link", "NOT_MET"), ("email.sender", "NOT_MET"))
    another = scored(("email.link", "NOT_MET"), learner=11)
    for sources in ((practice,), (reinforce,), (zero,), (another, practice)):
        request = project_topics(sources, ordering_error=False)
        assert request is not None
        assert TopicWireRequestV1.from_input(request).payload == PAYLOAD
        assert offline_recommendations(request) == (
            RECOMMENDATION_CATALOG["check_destination"][1],
            RECOMMENDATION_CATALOG["verify_sender_independently"][1],
        )
    left = project_topics((practice,), ordering_error=False)
    right = project_topics((reinforce,), ordering_error=False)
    assert left is not None and right is not None
    assert TopicWireRequestV1.from_input(left) == TopicWireRequestV1.from_input(right)


@pytest.mark.parametrize(
    "status",
    [
        "COMPLETED_PENDING_EVALUATION",
        "UNSCORABLE",
        "STORED_EVALUATION_INTEGRITY_ERROR",
        "IMMUTABLE_SOURCE_INTEGRITY_ERROR",
    ],
)
def test_latest_missing_unscorable_or_bad_source_supplies_no_topics(status):
    source = scored(("email.link", "MET"), score=100)
    latest = source.model_copy(
        update={
            "attempt_id": UUID(int=20),
            "completed_at": NOW + timedelta(hours=1),
            "result_status": status,
            "score": None,
            "criteria": (),
        }
    )
    selection = _select(
        [HistoricalAttempt(source, False, 1), HistoricalAttempt(latest, False, 1)],
        "LATEST_COMPLETED_PER_LEARNER",
    )
    assert [entry.detail for entry in selection] == [latest]
    assert (
        project_topics((entry.detail for entry in selection), ordering_error=False)
        is None
    )
    if status.endswith("INTEGRITY_ERROR"):
        assert project_topics((source, latest), ordering_error=False) is None
    assert offline_recommendations(None)


def test_empty_mixed_incompatible_or_ambiguous_slices():
    one = scored(("email.link", "NOT_MET"))
    other = scored(("email.link", "NOT_MET"), publication=21)
    incompatible = one.model_copy(update={"scoring_strategy": "different"})
    unknown = scored(("future.criterion", "NOT_MET"), ("email.link", "MET"))
    for sources in ((), (one, other), (one, incompatible), (unknown,)):
        assert project_topics(sources, ordering_error=False) is None
    assert project_topics((one,), ordering_error=True) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "assistant-input-v1"},
        {"schema_version": None},
        {"topics": []},
        {"topics": ["sender_verification", "link_inspection"]},
        {"topics": ["reporting", "reporting"]},
        {"topics": ["unexpected"]},
        {"topics": [1]},
        {"topics": "reporting"},
        {"learner_count": 1},
    ],
)
def test_input_is_closed_and_canonical(changes):
    with pytest.raises(ValidationError):
        AssistantTopicInputV1.model_validate_json(
            json.dumps(json.loads(PAYLOAD) | changes)
        )
    with pytest.raises(ValidationError):
        AssistantTopicInputV1.model_validate_json('{"topics":["reporting"]}')


def test_catalog_schema_and_rendering_agree():
    assert set(get_args(Topic)) == set(TOPIC_BY_CRITERION.values())
    assert set(get_args(RecommendationId)) == set(RECOMMENDATION_CATALOG)
    request = AssistantTopicInputV1.model_validate_json(PAYLOAD)
    wire = TopicWireRequestV1.from_input(request)
    assert wire.digest == WIRE_DIGEST
    schema = json.loads(wire.response_schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"schema_version", "recommendations"}
    item_schema = schema["$defs"]["TopicRecommendationV1"]
    assert item_schema["additionalProperties"] is False
    for identifier, (topic, _) in RECOMMENDATION_CATALOG.items():
        assert identifier in TOPIC_INSTRUCTIONS
        assert identifier in item_schema["properties"]["recommendation_id"]["enum"]
        assert topic in item_schema["properties"]["topic"]["enum"]
    answer = (
        '{"schema_version":"assistant-topic-selection-v1","recommendations":'
        '[{"topic":"sender_verification","recommendation_id":"check_sender_address"},'
        '{"topic":"link_inspection","recommendation_id":"use_known_address"}]}'
    )
    assert decode_selection(answer, request) == (
        RECOMMENDATION_CATALOG["check_sender_address"][1],
        RECOMMENDATION_CATALOG["use_known_address"][1],
    )
    for field in ("payload", "instructions", "response_schema"):
        assert replace(wire, **{field: "changed"}).digest != wire.digest


def test_wire_revalidates_the_payload():
    request = AssistantTopicInputV1.model_validate_json(PAYLOAD)
    corrupted = request.model_copy(update={"topics": ("unexpected",)})
    with pytest.raises(ValidationError):
        TopicWireRequestV1.from_input(corrupted)


@pytest.mark.parametrize(
    "answer",
    [
        '{"recommendations":[]}',
        '{"schema_version":"assistant-topic-selection-v2","recommendations":[]}',
        '{"schema_version":"assistant-topic-selection-v1","recommendations":[]}',
        '[{"topic":"link_inspection","recommendation_id":"wrong_id"}]',
        '[{"topic":"link_inspection","recommendation_id":"protect_credentials"}]',
        '[{"topic":"data_protection","recommendation_id":"protect_credentials"}]',
        '[{"topic":"link_inspection","recommendation_id":"check_destination","text":"x"}]',
        '[{"topic":"link_inspection","topic":"link_inspection",'
        '"recommendation_id":"check_destination"}]',
        '[{"topic":"link_inspection","recommendation_id":"check_destination"},'
        '{"topic":"link_inspection","recommendation_id":"use_known_address"}]',
        '"free text"',
    ],
)
def test_rejects_the_entire_invalid_response(answer):
    if not answer.startswith("{"):
        answer = (
            '{"schema_version":"assistant-topic-selection-v1",'
            '"recommendations":' + answer + "}"
        )
    with pytest.raises(ValueError):
        decode_selection(answer, AssistantTopicInputV1.model_validate_json(PAYLOAD))


def test_policy_scope_provider_revision_and_expiry_bind_separately_from_preview():
    profile = ProviderPrivacyProfileV1(
        profile_id="profile",
        credential_revision="revision",
        provider="groq",
        account_reference="account",
        endpoint="https://example.invalid",
        model="model",
        mode="approved-test",
    )
    policy = AdvisoryPolicyEvidenceV1(
        schema_version="advisory-policy-evidence-v1",
        purpose="instructor-topic-advisory",
        data_class="synthetic",
        scope_digest="a" * 64,
        provider_profile=profile,
        organization_decision="policy",
        provider_privacy_review="privacy-assessment",
        responsible_party="officer",
        assessed_at=NOW,
        expires_at=NOW + timedelta(days=1),
        revoked=False,
        residual_linkability_accepted=True,
    )
    context = {
        "scope_digest": policy.scope_digest,
        "provider_profile": profile,
        "data_class": "synthetic",
        "now": NOW,
    }
    assert policy.permits(**context)
    for changes in (
        {"data_class": "real"},
        {"scope_digest": "b" * 64},
        {"now": policy.expires_at},
        {"now": NOW - timedelta(seconds=1)},
        {"now": NOW.replace(tzinfo=None)},
        {"provider_profile": profile.model_copy(update={"credential_revision": "new"})},
    ):
        assert not policy.permits(**(context | changes))
    for changes in ({"revoked": True}, {"residual_linkability_accepted": False}):
        assert not policy.model_copy(update=changes).permits(**context)
    binding = AdvisoryPreviewBinding(
        "session", 1, policy.scope_digest, "c" * 64, policy, "d" * 64
    )
    assert replace(binding, ui_generation=2) != binding
    assert replace(binding, source_digest="e" * 64) != binding
    assert replace(binding, session_reference="another") != binding
