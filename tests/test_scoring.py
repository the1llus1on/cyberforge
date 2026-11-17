"""Production scorer parity with frozen independent WP1 vectors."""

import json
from decimal import localcontext
from pathlib import Path

import pytest

from cyberforge.evaluation.canonical import canonical_bytes
from cyberforge.evaluation.contracts import EvaluationEvidenceV1, EvaluationResultV1
from cyberforge.evaluation.scoring import ScoringService, numerical_paths_ready
from cyberforge.scenario_integration.contracts import RubricDefinitionV1, criterion

GOLD = Path(__file__).parent / "fixtures/evaluation"


@pytest.mark.parametrize(
    "name", ["safe", "web", "repeated", "reversed", "unscorable", "observations"]
)
def test_production_golden(name):
    raw = json.loads((GOLD / (name + ".json")).read_text())
    evidence = EvaluationEvidenceV1.model_validate_json(
        canonical_bytes(raw["evidence"])
    )
    expected = EvaluationResultV1.model_validate_json(canonical_bytes(raw["result"]))
    with localcontext() as ctx:
        ctx.prec = 2
        actual = ScoringService().score(
            evidence, result_id=expected.result_id, evaluated_at=expected.evaluated_at
        )
    assert canonical_bytes(actual) == canonical_bytes(expected)


@pytest.mark.parametrize(
    "ids,ready",
    [
        (("transition.decision",), False),
        (("transition.safe_decline",), True),
        (("email.sender",), True),
        (("transition.decision", "web.address"), False),
    ],
)
def test_prospective_paths(ids, ready):
    from types import SimpleNamespace

    assert (
        numerical_paths_ready(
            SimpleNamespace(criteria=tuple(criterion(i) for i in ids))
        )
        is ready
    )


def test_historical_loader_still_accepts_decision_only():
    raw = json.loads((GOLD / "unscorable.json").read_text())
    assert RubricDefinitionV1.model_validate(raw["sources"]["rubric"]).criteria


def source_case(name="web", *, selected=None, suppress=None, reverse=False):
    """Create source-valid strategy vectors from frozen synthetic source material."""
    from cyberforge.agents.contracts import EmailDraftV2
    from cyberforge.domain.scenarios import ScenarioParameters
    from cyberforge.learning.contracts import AttemptEventV1, ScenarioAttemptV1
    from cyberforge.scenario_integration.contracts import (
        InternalNavigationV1,
        ScenarioLinkV1,
        ScenarioPublicationManifestV1,
    )
    from cyberforge.web.contracts import WebDraftV3, fingerprint

    data = json.loads((GOLD / (name + ".json")).read_text())
    sources = data["sources"]
    rubric = RubricDefinitionV1.model_validate_json(json.dumps(sources["rubric"]))
    content = rubric.model_dump(mode="json", exclude={"content_digest"})
    if selected is not None:
        content["criteria"] = [
            criterion(i, weight=w).model_dump(mode="json") for i, w in selected
        ]
    if reverse:
        content["criteria"].reverse()
    rubric = RubricDefinitionV1.model_validate_json(
        json.dumps(content | {"content_digest": fingerprint(content)})
    )
    manifest = ScenarioPublicationManifestV1.model_validate_json(
        json.dumps(sources["manifest"])
    )
    content = manifest.model_dump(mode="json", exclude={"manifest_digest"})
    content["snapshot"]["rubric_digest"] = rubric.content_digest
    manifest = ScenarioPublicationManifestV1.model_validate_json(
        json.dumps(content | {"manifest_digest": fingerprint(content)})
    )
    a = sources["attempt"]
    a["manifest_digest"] = manifest.manifest_digest
    events = data["evidence"]["events"]
    for e in events:
        if suppress and (e["surface"], e["action_id"]) == suppress:
            e["action_id"] = (
                "email_opened"
                if e["surface"] == "email"
                else "report"
                if suppress[1] != "report"
                else "inspect_address"
            )
            if e["surface"] == "web":
                e["component_id"] = "browser:" + e["action_id"]
        if e["action_id"] == "started":
            operation = dict(action="started")
        else:
            navigation = (
                InternalNavigationV1(
                    publication_id=sources["publication_id"],
                    scenario_id=a["scenario_id"],
                    scenario_version=a["scenario_version"],
                    internal_resource_id=sources["web"]["page"]["internal_resource_id"],
                    manifest_digest=manifest.manifest_digest,
                ).model_dump(mode="json")
                if e["action_id"] == "open_internal"
                else None
            )
            operation = dict(
                surface=e["surface"],
                action_id=e["action_id"],
                component_id=e["component_id"],
                navigation=navigation,
                source_message_identifier="main" if navigation else None,
            )
        e["operation_digest"] = fingerprint(operation)
    if suppress == ("web", "leave"):
        a["decision"] = "NONE"
    sources.update(
        rubric=rubric,
        manifest=manifest,
        attempt=ScenarioAttemptV1.model_validate_json(json.dumps(a)),
        email=EmailDraftV2.model_validate_json(json.dumps(sources["email"])),
        web=WebDraftV3.model_validate_json(json.dumps(sources["web"])),
        link=ScenarioLinkV1.model_validate_json(json.dumps(sources["link"])),
        parameters=ScenarioParameters.model_validate_json(
            json.dumps(sources["parameters"])
        ),
    )
    return sources, tuple(
        AttemptEventV1.model_validate_json(json.dumps(e)) for e in events
    )


@pytest.mark.parametrize(
    "identifier,surface,action",
    [
        ("email.sender", "email", "inspect_sender"),
        ("email.link", "email", "inspect_link"),
        ("email.report", "email", "report"),
        ("web.address", "web", "inspect_address"),
        ("web.leave", "web", "leave"),
        ("web.report", "web", "report"),
    ],
)
@pytest.mark.parametrize("met", [False, True])
def test_independent_action_criteria(identifier, surface, action, met):
    sources, events = source_case(suppress=None if met else (surface, action))
    scorer = ScoringService()
    result = scorer.score(scorer.evidence(events=events, **sources))
    assert next(
        c.score for c in result.criteria if c.criterion.criterion_id == identifier
    ) == int(met)


@pytest.mark.parametrize(
    "n,d,expected",
    [
        (1.0, 32.0, "3.12"),
        (3.0, 32.0, "9.38"),
        (1.0, 3.0, "33.33"),
        (5e-324, 10000.0, "0.00"),
        (10000.0, 10001.0, "99.99"),
    ],
)
def test_production_exact_weights_half_even(n, d, expected):
    sources, events = source_case(
        selected=[("email.sender", n), ("transition.safe_decline", d - n)]
    )
    result = ScoringService().score(ScoringService().evidence(events=events, **sources))
    assert format(result.score_percent, ".2f") == expected
    from decimal import Decimal
    from fractions import Fraction

    assert Fraction(result.weighted_numerator) == Fraction(Decimal(str(n)))
    assert Fraction(result.weighted_denominator) == Fraction(
        Decimal(str(n))
    ) + Fraction(Decimal(str(d - n)))


def test_source_order_is_arithmetic_invariant_with_distinct_digests():
    scorer = ScoringService()
    sources, events = source_case()
    other, other_events = source_case(reverse=True)
    first = scorer.score(scorer.evidence(events=events, **sources))
    second = scorer.score(scorer.evidence(events=other_events, **other))
    assert first.criteria == second.criteria
    assert first.score_percent == second.score_percent
    assert first.weighted_denominator == second.weighted_denominator
    assert first.evidence_digest != second.evidence_digest
    assert first.source.snapshot.rubric_digest != second.source.snapshot.rubric_digest


@pytest.mark.parametrize(
    "case",
    [
        "gap",
        "foreign",
        "duplicate",
        "order",
        "provenance",
        "no_visit",
        "rubric_version",
        "source_id",
    ],
)
def test_production_rejects_invalid_sources_and_histories(case):
    from uuid import uuid4

    sources, events = source_case()
    events = list(events)
    if case == "gap":
        events.pop(2)
    if case == "foreign":
        events[2] = events[2].model_copy(update={"attempt_id": uuid4()})
    if case == "duplicate":
        events[2] = events[2].model_copy(update={"event_id": events[1].event_id})
    if case == "order":
        events[2], events[3] = events[3], events[2]
    if case == "provenance":
        i = next(i for i, e in enumerate(events) if e.surface == "web")
        events[i] = events[i].model_copy(update={"component_id": "untrusted_component"})
    if case == "no_visit":
        events = [e for e in events if e.action_id != "web_entered"]
    if case == "rubric_version":
        sources["rubric"] = sources["rubric"].model_copy(
            update={"semantics_version": "unknown"}
        )
    if case == "source_id":
        sources["publication_id"] = 9999
    with pytest.raises(ValueError):
        ScoringService().evidence(events=events, **sources)
