"WP1 source-valid golden vectors and hostile contract projections, offline."

import hashlib
import importlib
import json
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from cyberforge.application.learner_attempts import (
    AttemptEventService,
    LearnerAttemptService,
)
from cyberforge.application.learner_demo import demo_web_actions
from cyberforge.evaluation.canonical import (
    canonical_bytes,
    digest,
    historical_weight,
    parse_contract,
    reference_arithmetic,
)
from cyberforge.evaluation.contracts import (
    CriterionEvaluationV1,
    EvaluationErrorV1,
    EvaluationEvidenceV1,
    EvaluationResultV1,
    EvaluationSourceV1,
    LocalMentorFeedbackV1,
)
from cyberforge.evaluation.facts import (
    CATALOGUE,
    OBJECTIVE,
    deterministic_explanation,
    project_facts,
    validate_feedback_against_result,
)
from cyberforge.evaluation.validation import (
    evidence_projection,
    validate_result_against_evidence,
    validate_sources,
)
from cyberforge.scenario_integration.contracts import CRITERIA, criterion
from tests.test_scenario_integration import (  # noqa: F401
    confirm,
    link,
    materials,
    publication_env,
)

BASE = datetime(2026, 11, 17, tzinfo=UTC)
GOLD = Path(__file__).parent / "fixtures" / "evaluation"


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return BASE if tz else BASE.replace(tzinfo=None)

    counter = iter(range(1, 10000))
    for name in (
        "scenarios",
        "email_materials",
        "web_materials",
        "scenario_integration",
        "scenario_readiness",
        "scenario_publication",
        "learner_attempts",
    ):
        module = importlib.import_module("cyberforge.application." + name)
        monkeypatch.setattr(module, "datetime", Clock)
        if hasattr(module, "uuid4"):
            monkeypatch.setattr(module, "uuid4", lambda: UUID(int=next(counter)))


def oracle_tree(value, name=""):
    # Independent test implementation, using different decimal/time operations.
    if isinstance(value, BaseModel):
        return {n: oracle_tree(getattr(value, n), n) for n in type(value).model_fields}
    if isinstance(value, Decimal):
        if name == "score_percent":
            return format(value, ".2f")
        text = str(value) if value == value.to_integral_value() else format(value, "f")
        text = format(Decimal(text), "f")
        return (text.rstrip("0").rstrip(".") if "." in text else text) if value else "0"
    if isinstance(value, datetime):
        return (
            value.astimezone(UTC)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [oracle_tree(v) for v in value]
    if isinstance(value, dict):
        return {k: oracle_tree(v, k) for k, v in value.items()}
    return value


def oracle_digest(value, exclude=None):
    tree = oracle_tree(value)
    if exclude:
        tree.pop(exclude)
    return hashlib.sha256(
        json.dumps(
            tree,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def seal(model, fields, field):
    # Validate a real completed object, never model_construct/model_copy bypass.
    return model.model_validate_json(
        canonical_bytes(fields | {field: oracle_digest(fields)})
    )


@pytest.fixture(
    params=("safe", "web", "reversed", "repeated", "unscorable", "observations")
)
def bundle(request, publication_env):  # noqa: F811
    e = publication_env
    name = request.param
    materials(e)
    # Existing app-owned actions, validated and saved before immutable publication.
    ww = e.webs.load(e.token, e.scenario)
    e.saved_web = e.webs.save(e.token, ww, demo_web_actions(e.saved_web.draft))
    link(e)
    selected = (
        (criterion("transition.decision"),)
        if name == "unscorable"
        else tuple(criterion(c.id) for c in CRITERIA)
    )
    e.integration.save_rubric(e.token, e.scenario, selected, expected_revision=0)
    receipt = confirm(e)
    publication = e.publications.publish(
        e.token, e.scenario, confirmation_id=receipt.confirmation_id
    )
    _, state = e.access.content(e.tokens["learner"], publication.id)
    attempts = LearnerAttemptService(e.access)
    actions = AttemptEventService(attempts)
    token = e.tokens["learner"]
    a = attempts.start_or_resume(token, e.scenario.id)
    request_counter = iter(range(10000, 20000))

    def act(surface, action, component=None):
        nonlocal a
        kw = dict(
            request_id=UUID(int=next(request_counter)), expected_revision=a.revision
        )
        if action == "web_entered":
            a = actions._display_acknowledger(token, a.attempt_id)(**kw)
        elif surface == "web" and component is None:
            a = actions.browser_control(token, a.attempt_id, control=action, **kw)
        else:
            if action == "open_internal":
                kw.update(
                    navigation=e.access.resolve_internal(token, publication.id),
                    source_message_identifier="main",
                )
            a = actions.record(
                token,
                a.attempt_id,
                surface=surface,
                action_id=action,
                component_id=component,
                **kw,
            )

    act("email", "email_opened")
    if name != "unscorable":
        for action in ("inspect_sender", "inspect_link", "report"):
            for _ in range(2 if name == "repeated" else 1):
                act("email", action)
    if name in ("safe", "unscorable", "reversed"):
        act("transition", "decline")
    if name not in ("safe", "unscorable"):
        act("transition", "open_internal")
        act("system", "web_entered")
        for action in ("inspect_address", "report"):
            for _ in range(2 if name == "repeated" else 1):
                act("web", action)
        if name == "observations":
            act("web", "confirm", "learner_actions")
            act("web", "submit_synthetic", "demo_form")
        for _ in range(2 if name == "repeated" else 1):
            act("web", "leave")
    act("system", "completed")
    events = attempts.events(token, a.attempt_id)
    source = EvaluationSourceV1(
        schema_version="evaluation-source-v1",
        publication_id=publication.id,
        version_id=state.version_id,
        manifest_schema_version="scenario-publication-v1",
        manifest_digest=publication.manifest.manifest_digest,
        snapshot=publication.manifest.snapshot,
        rubric_id=state.rubric.rubric_id,
        rubric_schema_version="rubric-definition-v1",
        registry_version="criterion-registry-v1",
        rubric_semantics_version="rubric-declarations-v1",
    )
    path, transition, criteria, observations = evidence_projection(
        a, events, state.rubric.criteria
    )
    ev = seal(
        EvaluationEvidenceV1,
        dict(
            schema_version="evaluation-evidence-v1",
            attempt=a,
            source=source,
            scoring_strategy="cyberforge-weighted-actions-v1",
            events=events,
            event_count=len(events),
            terminal_sequence=len(events),
            events_digest=oracle_digest(events),
            path=path,
            transition=transition,
            criteria=criteria,
            critical_policy_status="NOT_CONFIGURED",
            critical_observations=observations,
        ),
        "evidence_digest",
    )
    sources = dict(
        manifest=publication.manifest,
        rubric=state.rubric,
        email=state.email,
        web=state.web,
        link=state.link,
        parameters=state.scenario.parameters,
        version_id=state.version_id,
        publication_id=publication.id,
        attempt=a,
    )
    validate_sources(ev, **sources)
    details = []
    for i, c in enumerate(criteria):
        descriptive = c.criterion.criterion_id == "transition.decision"
        score = None if descriptive or not c.applicable else int(c.condition_satisfied)
        details.append(
            CriterionEvaluationV1(
                schema_version="criterion-evaluation-v1",
                position=i,
                criterion=c.criterion,
                applicable=c.applicable,
                outcome="DESCRIPTIVE"
                if descriptive
                else "NOT_APPLICABLE"
                if not c.applicable
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
                descriptive_transition=transition if descriptive else None,
            )
        )
    # Independent Fraction arithmetic rather than the production verification helper.
    n = sum(
        (
            Fraction(c.criterion.weight) * c.score
            for c in details
            if c.score is not None
        ),
        Fraction(0),
    )
    d = sum(
        (Fraction(c.criterion.weight) for c in details if c.score is not None),
        Fraction(0),
    )
    percent = (
        None
        if not d
        else Decimal(str(round(100 * n / d, 2).numerator))
        / Decimal(str(round(100 * n / d, 2).denominator))
    )
    result_fields = {
        k: getattr(ev, k)
        for k in (
            "attempt",
            "source",
            "scoring_strategy",
            "event_count",
            "terminal_sequence",
            "events_digest",
            "evidence_digest",
            "path",
            "transition",
            "critical_policy_status",
            "critical_observations",
        )
    }
    result_fields.update(
        schema_version="evaluation-result-v1",
        result_id=UUID(int=20000),
        criteria=tuple(details),
        status="SCORED" if d else "UNSCORABLE",
        reason_code=None if d else "NO_APPLICABLE_NUMERICAL_CRITERIA",
        weighted_numerator=Decimal(n.numerator) / Decimal(n.denominator),
        weighted_denominator=Decimal(d.numerator) / Decimal(d.denominator),
        score_percent=percent,
        evaluated_at=BASE,
    )
    result = seal(EvaluationResultV1, result_fields, "result_digest")
    validate_result_against_evidence(result, ev, details=details)
    facts, topics = project_facts(result)
    feedback = seal(
        LocalMentorFeedbackV1,
        dict(
            schema_version="local-mentor-feedback-v1",
            feedback_id=UUID(int=20001),
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
            mode="DETERMINISTIC",
            fallback_reason="CLOUD_DISABLED" if d else "UNSCORABLE",
            provider=None,
            model=None,
            explanation=deterministic_explanation(result),
            created_at=BASE,
        ),
        "feedback_digest",
    )
    validate_feedback_against_result(feedback, result)
    return name, ev, result, feedback, sources


def test_source_valid_golden(bundle):
    name, ev, result, feedback, sources = bundle
    actual = {
        "evidence": oracle_tree(ev),
        "result": oracle_tree(result),
        "feedback": oracle_tree(feedback),
        "sources": {k: oracle_tree(v) for k, v in sources.items()},
    }
    assert actual == json.loads((GOLD / (name + ".json")).read_text())
    for obj, own in (
        (ev, "evidence_digest"),
        (result, "result_digest"),
        (feedback, "feedback_digest"),
    ):
        assert getattr(obj, own) == oracle_digest(obj, own)
        assert canonical_bytes(
            parse_contract(type(obj), canonical_bytes(obj))
        ) == canonical_bytes(obj)
    expected = (
        (4, 4, "100.00")
        if name == "safe"
        else (0, 0, None)
        if name == "unscorable"
        else (6, 7, "85.71")
    )
    assert (
        result.weighted_numerator,
        result.weighted_denominator,
        None if result.score_percent is None else format(result.score_percent, ".2f"),
    ) == expected
    assert result.path.event_refs[-1].sequence == ev.event_count
    if name == "reversed":
        assert len(result.transition.event_refs) == 2
    if name == "repeated":
        assert ev.event_count == 17
        assert [r.sequence for r in ev.criteria[0].supporting_event_refs] == [3, 4]
    if name == "observations":
        assert len(result.critical_observations) == 2


@pytest.mark.parametrize(
    "target", ["event", "path", "criterion", "result", "detail", "source", "feedback"]
)
def test_corrupt_projection_rejected(bundle, target):
    _, ev, res, fb, sources = bundle
    if target == "event":
        data = oracle_tree(ev)
        data["events"][0]["attempt_id"] = str(UUID(int=999))
        with pytest.raises(ValueError):
            EvaluationEvidenceV1.model_validate_json(canonical_bytes(data))
    elif target == "path":
        data = oracle_tree(ev)
        data["path"]["event_refs"][0]["sequence"] = 999
        data["evidence_digest"] = oracle_digest(
            {k: v for k, v in data.items() if k != "evidence_digest"}
        )
        with pytest.raises(ValueError):
            EvaluationEvidenceV1.model_validate_json(canonical_bytes(data))
    elif target == "criterion":
        data = oracle_tree(ev)
        data["criteria"][0]["criterion"]["weight"] = "2"
        data["evidence_digest"] = oracle_digest(
            {k: v for k, v in data.items() if k != "evidence_digest"}
        )
        forged = EvaluationEvidenceV1.model_validate_json(canonical_bytes(data))
        with pytest.raises(ValueError):
            validate_sources(forged, **sources)
    elif target == "result":
        data = oracle_tree(res)
        data["weighted_denominator"] = "99"
        data["result_digest"] = oracle_digest(
            {k: v for k, v in data.items() if k != "result_digest"}
        )
        with pytest.raises(ValueError):
            EvaluationResultV1.model_validate_json(canonical_bytes(data))
    elif target == "detail":
        for details in (
            res.criteria[:-1],
            res.criteria + res.criteria[:1],
            *((tuple(reversed(res.criteria)),) if len(res.criteria) > 1 else ()),
        ):
            with pytest.raises(ValueError):
                validate_result_against_evidence(res, ev, details=details)
    elif target == "source":
        with pytest.raises(ValueError):
            validate_sources(ev, **(sources | {"version_id": 999}))
    else:
        data = oracle_tree(fb)
        data["facts"][0]["explanation"] = "Безпідставне твердження."
        with pytest.raises(ValueError):
            LocalMentorFeedbackV1.model_validate_json(canonical_bytes(data))


@pytest.mark.parametrize(
    "raw",
    [
        '{"event_id":"00000000-0000-0000-0000-000000000001","sequence":true}',
        '{"event_id":"00000000-0000-0000-0000-000000000001","sequence":1,"sequence":1}',
        '{"event_id":"00000000-0000-0000-0000-000000000001","sequence":1.0}',
    ],
)
def test_strict_reference_boundary(raw):
    from cyberforge.evaluation.contracts import EvaluationEventReferenceV1

    with pytest.raises(ValueError):
        parse_contract(EvaluationEventReferenceV1, raw)


@pytest.mark.parametrize(
    "n,d,expected",
    [
        ("1", "32", "3.12"),
        ("3", "32", "9.38"),
        ("1", "3", "33.33"),
        ("0", "1", "0.00"),
        ("0.1", "0.3", "33.33"),
    ],
)
def test_rounding(n, d, expected):
    items = (
        ((Decimal(n), 1), (Decimal(d) - Decimal(n), 0))
        if n != "0"
        else ((Decimal(d), 0),)
    )
    with localcontext() as context:
        context.prec = 2
        assert format(reference_arithmetic(items)[2], ".2f") == expected


def test_tiny_weights_and_registry_catalogue():
    with localcontext() as context:
        context.prec = 1
        n, d, p = reference_arithmetic(
            ((historical_weight(5e-324), 1), (historical_weight(1e4), 0))
        )
    assert n == Decimal("5e-324") and d > 10000 and p == 0
    assert all(f.defensive_behavior for f in CATALOGUE)
    text = next(
        f.explanation
        for f in CATALOGUE
        if f.fact_id == "transition_safe_decline_not_met"
    )
    assert text == (
        "Перехід до Web не підтверджує фінальну відмову від "
        "переходу, незалежно від попередніх рішень."
    )


def test_reference_hash_and_immutability():
    from cyberforge.evaluation.contracts import EvaluationEventReferenceV1

    r = EvaluationEventReferenceV1(event_id=UUID(int=1), sequence=1)
    assert (
        digest(r) == "6de80492ffba53d16d69d30071e20d22dcfafd00be06c6180d867504dd8aa628"
    )
    with pytest.raises(ValidationError):
        r.sequence = 2


def test_error_semantics():
    fields = dict(
        schema_version="evaluation-error-v1",
        operation="read",
        code="STORED_EVALUATION_INTEGRITY_ERROR",
        retryable=False,
        correlation_id=UUID(int=1),
        attempt_id=UUID(int=2),
        result_id=None,
        integrity_reason="IMMUTABLE_SOURCE_MISSING",
    )
    error = EvaluationErrorV1(**fields)
    assert parse_contract(EvaluationErrorV1, canonical_bytes(error)) == error
    for bad in (
        {"retryable": True},
        {"integrity_reason": None},
        {"code": "ACCESS_DENIED"},
    ):
        with pytest.raises(ValidationError):
            EvaluationErrorV1(**(fields | bad))


def test_original_synthetic_hash_fixture():
    data = json.loads((GOLD / "synthetic_hashing.json").read_text())
    ev = EvaluationEvidenceV1.model_validate_json(canonical_bytes(data["evidence"]))
    result = EvaluationResultV1.model_validate_json(canonical_bytes(data["result"]))
    validate_result_against_evidence(result, ev)
    assert (
        digest(()) == "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    )
    assert (
        ev.events_digest
        == "1e13d0b69c7bf8789d564c8c23ebaeb3c91ee61640051ef2af4b3f68789056ec"
    )
    assert (
        ev.evidence_digest
        == "6300955dbd5dd613369483cb416e821c3a4ab77b595489a8a85e5670dab1f9b1"
    )
    assert (
        result.result_digest
        == "dbf253ea84221d9fe3890a7a7449967c13279676a791e043c82f6b3f28b20e2e"
    )


@pytest.mark.parametrize(
    "case",
    [
        "unknown_strategy",
        "missing_null",
        "extra",
        "decimal_exponent",
        "timestamp_offset",
        "duplicate",
        "unknown_criterion",
        "fraction_score",
        "negative_weight",
        "unsupported_claim",
    ],
)
def test_frozen_wire_rejects(case):
    data = json.loads((GOLD / "safe.json").read_text())
    model = EvaluationResultV1
    value = data["result"]
    if case == "unknown_strategy":
        value["scoring_strategy"] = "next-version"
    elif case == "missing_null":
        value.pop("reason_code")
    elif case == "extra":
        value["user_annotation"] = "arbitrary"
    elif case == "decimal_exponent":
        value["criteria"][0]["criterion"]["weight"] = "1e0"
    elif case == "timestamp_offset":
        value["evaluated_at"] = "2026-11-17T01:00:00.000000+01:00"
    elif case == "duplicate":
        value["criteria"].append(value["criteria"][0])
    elif case == "unknown_criterion":
        value["criteria"][0]["criterion"]["criterion_id"] = "email.interpretation"
    elif case == "fraction_score":
        value["criteria"][0]["score"] = 0.5
    elif case == "negative_weight":
        value["criteria"][0]["criterion"]["weight"] = "-1"
    else:
        model = LocalMentorFeedbackV1
        value = data["feedback"]
        value["explanation"]["limitations"].append("Учень неуважний.")
    own = "feedback_digest" if model is LocalMentorFeedbackV1 else "result_digest"
    value[own] = oracle_digest({k: v for k, v in value.items() if k != own})
    with pytest.raises(ValueError):
        model.model_validate_json(canonical_bytes(value))


def test_stored_pipeline_and_feedback_consumption(bundle):
    from cyberforge.evaluation.validation import validate_stored_projection

    _, ev, r, f, sources = bundle
    assert validate_stored_projection(r, ev, details=r.criteria, **sources) == r
    validate_feedback_against_result(f, r)
    for wrong in ({"publication_id": 999}, {"version_id": 999}):
        with pytest.raises(ValueError):
            validate_stored_projection(r, ev, details=r.criteria, **(sources | wrong))
    assert "raw_events" not in canonical_bytes(f).decode()
    # Fixed catalogue data contains neither local identities nor source title.
    assert all(
        str(ev.attempt.attempt_id) not in fact.observation + fact.explanation
        for fact in f.facts
    )


def test_selection_order_arithmetic_vs_source_identity():
    from cyberforge.scenario_integration.contracts import RubricDefinitionV1

    data = json.loads((GOLD / "safe.json").read_text())
    rubric_data = data["sources"]["rubric"]
    rubric = RubricDefinitionV1.model_validate_json(json.dumps(rubric_data))
    reverse = dict(rubric_data, criteria=list(reversed(rubric_data["criteria"])))
    # Existing fingerprint uses accepted datetime formatting, unchanged.
    content = rubric.model_dump(mode="json", exclude={"content_digest"})
    content["criteria"] = list(reversed(content["criteria"]))
    from cyberforge.web.contracts import fingerprint

    reverse["content_digest"] = fingerprint(content)
    other = RubricDefinitionV1.model_validate_json(json.dumps(reverse))
    ev = EvaluationEvidenceV1.model_validate_json(canonical_bytes(data["evidence"]))
    assert evidence_projection(
        ev.attempt, ev.events, rubric.criteria
    ) == evidence_projection(ev.attempt, ev.events, other.criteria)
    assert rubric.content_digest != other.content_digest
    altered = oracle_tree(ev)
    altered["source"]["snapshot"]["rubric_digest"] = other.content_digest
    altered["evidence_digest"] = oracle_digest(
        {k: v for k, v in altered.items() if k != "evidence_digest"}
    )
    assert altered["evidence_digest"] != ev.evidence_digest


@pytest.mark.parametrize(
    "code,retry",
    [
        ("STORAGE_BUSY", True),
        ("STORAGE_UNAVAILABLE", True),
        ("SOURCE_UNAVAILABLE", True),
        ("STORAGE_FAILURE", False),
        ("UNSUPPORTED_VERSION", False),
    ],
)
def test_transient_vs_permanent_errors(code, retry):
    error = EvaluationErrorV1(
        schema_version="evaluation-error-v1",
        operation="evaluate",
        code=code,
        retryable=retry,
        correlation_id=UUID(int=1),
        attempt_id=None,
        result_id=None,
        integrity_reason=None,
    )
    assert parse_contract(EvaluationErrorV1, canonical_bytes(error)) == error
    with pytest.raises(ValidationError):
        EvaluationErrorV1(**(error.model_dump() | {"retryable": not retry}))


def test_candidate_schema_snapshot():
    from pydantic import TypeAdapter

    from cyberforge.evaluation import contracts as c

    names = (
        "EvaluationSourceV1",
        "EvaluationCriterionSnapshotV1",
        "CompletedPathV1",
        "TransitionDecisionV1",
        "EvaluationEventReferenceV1",
        "CriterionEvidenceV1",
        "CriticalObservationV1",
        "EvaluationEvidenceV1",
        "CriterionEvaluationV1",
        "EvaluationResultV1",
        "LocalMentorFeedbackV1",
        "EvaluationErrorV1",
    )
    union = getattr(c, names[0])
    for name in names[1:]:
        union = union | getattr(c, name)
    assert TypeAdapter(union).json_schema() == json.loads(
        (GOLD / "contracts.schema.json").read_text()
    )
    for name in names:
        assert all(f.is_required() for f in getattr(c, name).model_fields.values())


@pytest.mark.parametrize("valid_selection", [True, False])
def test_existing_mentor_mock_compatibility_and_fallback(monkeypatch, valid_selection):
    import socket

    from cyberforge.agents.contracts import MentorInputV1
    from cyberforge.agents.demo import scripted_gateway
    from cyberforge.agents.specialized import MentorAgent

    monkeypatch.setattr(
        socket.socket,
        "connect",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("network forbidden")),
    )
    data = json.loads((GOLD / "web.json").read_text())
    r = EvaluationResultV1.model_validate_json(canonical_bytes(data["result"]))
    f = LocalMentorFeedbackV1.model_validate_json(canonical_bytes(data["feedback"]))
    source = MentorInputV1(
        synthetic=True,
        objective=OBJECTIVE,
        facts=f.facts,
        permitted_topics=f.permitted_topics,
        result=f.explanation.result,
    )
    payload = dict(
        schema_version="explanation-selection-v1",
        fact_ids=[x.fact_id for x in f.facts]
        if valid_selection
        else ["invented_claim"],
        recommended_topics=list(f.permitted_topics),
        evidence="supplied_facts",
        difficulty_suggestion="keep",
    )
    gateway, mock = scripted_gateway(payload)
    generated = MentorAgent(gateway).run(source)
    assert mock.calls == 1
    if valid_selection:
        fields = f.model_dump(exclude={"feedback_digest"}) | dict(
            mode="MODEL_SELECTION",
            fallback_reason=None,
            provider="mock",
            model="mock-v1",
            explanation=generated.draft,
        )
        model_feedback = seal(LocalMentorFeedbackV1, fields, "feedback_digest")
        validate_feedback_against_result(model_feedback, r)
        assert generated.status == "pending_review"
    else:
        assert generated.status == "failed"
        fields = f.model_dump(exclude={"feedback_digest"}) | dict(
            fallback_reason="INVALID_SELECTION"
        )
        offline = seal(LocalMentorFeedbackV1, fields, "feedback_digest")
        validate_feedback_against_result(offline, r)
        assert offline.explanation == f.explanation


def test_legacy_instance_cannot_smuggle_mutable_nested_data():
    from cyberforge.agents.contracts import ExplanationV1

    raw = json.loads((GOLD / "web.json").read_text())["feedback"]
    original = LocalMentorFeedbackV1.model_validate_json(canonical_bytes(raw))
    fields = original.explanation.model_dump()
    mutable = list(original.explanation.selected_facts)
    fields.update(selected_facts=mutable, result=original.explanation.result)
    forged = ExplanationV1.model_construct(**fields)
    feedback_fields = original.model_dump(exclude={"feedback_digest"})
    feedback_fields.update(
        mode="MODEL_SELECTION",
        fallback_reason=None,
        provider="mock",
        model="mock-v1",
        explanation=forged,
    )
    safe = seal(LocalMentorFeedbackV1, feedback_fields, "feedback_digest")
    assert type(safe.explanation.selected_facts) is tuple
    mutable.clear()
    assert safe.explanation.selected_facts == original.explanation.selected_facts
    assert safe.explanation is not forged
