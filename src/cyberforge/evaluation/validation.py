"""Pure checks over supplied immutable sources. No database or authorization API."""

from cyberforge.agents.contracts import EmailDraftV2
from cyberforge.learning.contracts import BROWSER_PREFIX
from cyberforge.scenario_integration.contracts import (
    CRITERIA,
    InternalNavigationV1,
    RubricDefinitionV1,
    ScenarioLinkV1,
    ScenarioPublicationManifestV1,
)
from cyberforge.web.contracts import WebDraftV3, email_digest, fingerprint

from .canonical import canonical_bytes, digest
from .contracts import (
    CompletedPathV1,
    CriterionEvidenceV1,
    CriticalObservationV1,
    EvaluationCriterionSnapshotV1,
    EvaluationEventReferenceV1,
    TransitionDecisionV1,
)


def require(condition, code):
    if not condition:
        raise ValueError(code)


def ref(event):
    return EvaluationEventReferenceV1(event_id=event.event_id, sequence=event.sequence)


def validate_binding(attempt, source):
    s = source.snapshot
    require(
        attempt.status == "COMPLETED" and attempt.completed_at is not None,
        "completed_attempt_required",
    )
    require(
        (
            attempt.publication_id,
            attempt.scenario_id,
            attempt.scenario_version,
            attempt.manifest_digest,
        )
        == (
            source.publication_id,
            s.scenario_id,
            s.scenario_version,
            source.manifest_digest,
        ),
        "attempt_source_binding",
    )


def validate_criterion_order(values):
    ids = [v.criterion.criterion_id for v in values]
    order = {c.id: i for i, c in enumerate(CRITERIA)}
    require(ids == sorted(set(ids), key=order.__getitem__), "criterion_order")


def replay(attempt, events):
    require(len(events) == attempt.last_event_sequence, "event_count")
    require(len({e.event_id for e in events}) == len(events), "duplicate_event")
    stage, opened, visited, decision = "EMAIL", False, False, "NONE"
    requests = set()
    for i, e in enumerate(events, 1):
        require(
            e.attempt_id == attempt.attempt_id
            and e.sequence == i
            and e.timestamp >= attempt.started_at,
            "event_binding_sequence_time",
        )
        # Accepted Phase9 commands append one event; replayed requests append none.
        require(
            e.request_id not in requests and e.operation_index == 0,
            "request_operation_group",
        )
        requests.add(e.request_id)
        if i == 1:
            require(
                (e.surface, e.action_id, e.timestamp)
                == ("system", "started", attempt.started_at),
                "started_event",
            )
        elif e.surface == "email":
            require(
                stage == "EMAIL" and (e.action_id == "email_opened" or opened),
                "email_lifecycle",
            )
            opened = True
        elif e.surface == "transition":
            require(stage == "EMAIL" and opened, "transition_lifecycle")
            if e.action_id == "decline":
                decision = "DECLINED"
            else:
                stage, decision = "WEB", "NONE"
        elif e.surface == "web":
            require(stage == "WEB" and visited, "web_before_display")
            if e.action_id == "leave":
                decision = "LEFT"
        elif e.action_id == "web_entered":
            require(stage == "WEB", "display_before_transition")
            visited = True
        elif e.action_id == "completed":
            require(
                i == len(events)
                and e.timestamp == attempt.completed_at
                and (
                    (stage == "EMAIL" and decision == "DECLINED")
                    or (stage == "WEB" and visited)
                ),
                "completion_lifecycle",
            )
        else:
            raise ValueError("unsupported_terminal_history")
    require(events[-1].action_id == "completed", "terminal_event")
    require(
        (stage, opened, visited, decision)
        == (
            attempt.current_stage,
            attempt.email_opened,
            attempt.web_visited,
            attempt.decision,
        ),
        "replayed_state",
    )
    require(attempt.revision == len(events) + 1, "attempt_revision")


def evidence_projection(attempt, events, declarations):
    """Expected factual projection for contract validation, never a score service."""
    replay(attempt, events)
    decisions = tuple(e for e in events if e.surface == "transition")
    require(bool(decisions), "transition_missing")
    no_web = not attempt.web_visited
    path_events = (
        (decisions[-1], events[-1])
        if no_web
        else (
            next(e for e in decisions if e.action_id == "open_internal"),
            next(e for e in events if e.action_id == "web_entered"),
            events[-1],
        )
    )
    path = CompletedPathV1(
        schema_version="completed-path-v1",
        kind="SAFE_DECLINE" if no_web else "WEB_VISITED",
        event_refs=tuple(map(ref, path_events)),
    )
    transition = TransitionDecisionV1(
        schema_version="transition-decision-v1",
        final_action_id=decisions[-1].action_id,
        event_refs=tuple(map(ref, decisions)),
    )
    result = []
    order = {c.id: i for i, c in enumerate(CRITERIA)}
    for declaration in sorted(declarations, key=lambda c: order[c.criterion_id]):
        c = (
            declaration
            if isinstance(declaration, EvaluationCriterionSnapshotV1)
            else EvaluationCriterionSnapshotV1.from_declaration(declaration)
        )
        applies = (
            c.applicability == "all_attempts"
            or (c.applicability == "web_visited" and not no_web)
            or (c.applicability == "web_not_visited" and no_web)
        )
        descriptive = c.criterion_id == "transition.decision"
        supporting = ()
        if descriptive:
            supporting = transition.event_refs
        elif applies:
            if c.criterion_id == "transition.safe_decline":
                supporting = path.event_refs if no_web else ()
            else:
                supporting = tuple(
                    ref(e)
                    for e in events
                    if e.surface == c.phase and e.action_id in c.evidence_actions
                )
        result.append(
            CriterionEvidenceV1(
                schema_version="criterion-evidence-v1",
                criterion=c,
                applicable=applies,
                condition_satisfied=None
                if descriptive or not applies
                else bool(supporting),
                supporting_event_refs=supporting,
            )
        )
    observations = tuple(
        CriticalObservationV1(
            schema_version="critical-observation-v1",
            event_ref=ref(e),
            surface="web",
            action_id=e.action_id,
            component_id=e.component_id,
            provenance="authored_component",
            observed_at=e.timestamp,
            critical_policy_status="NOT_CONFIGURED",
        )
        for e in events
        if e.surface == "web" and e.action_id in ("confirm", "submit_synthetic")
    )
    return path, transition, tuple(result), observations


def validate_evidence_structure(value):
    validate_binding(value.attempt, value.source)
    validate_criterion_order(value.criteria)
    require(
        value.event_count == value.terminal_sequence == len(value.events),
        "event_count_terminal",
    )
    expected = evidence_projection(
        value.attempt, value.events, tuple(c.criterion for c in value.criteria)
    )
    require(
        expected
        == (value.path, value.transition, value.criteria, value.critical_observations),
        "evidence_projection",
    )
    require(
        digest(value.events) == value.events_digest
        and digest(value, exclude="evidence_digest") == value.evidence_digest,
        "evidence_digest",
    )


def validate_sources(
    value,
    *,
    manifest,
    rubric,
    email,
    web,
    link,
    parameters,
    version_id,
    publication_id,
    attempt,
):
    """Caller supplies exact loaded sources; this function cannot grant access."""
    manifest = ScenarioPublicationManifestV1.model_validate_json(
        manifest.model_dump_json()
    )
    rubric = RubricDefinitionV1.model_validate_json(rubric.model_dump_json())
    email = EmailDraftV2.model_validate_json(email.model_dump_json())
    web = WebDraftV3.model_validate_json(web.model_dump_json())
    link = ScenarioLinkV1.model_validate_json(link.model_dump_json())
    s = manifest.snapshot
    require(
        type(publication_id) is int
        and publication_id > 0
        and type(version_id) is int
        and version_id > 0,
        "source_identity_type",
    )
    require(
        value.attempt == attempt and value.source.publication_id == publication_id,
        "authoritative_attempt_publication",
    )
    require(
        (email.scenario_id, email.scenario_version)
        == (s.scenario_id, s.scenario_version),
        "email_source",
    )
    require(
        value.source.version_id == version_id
        and value.source.manifest_digest == manifest.manifest_digest
        and value.source.snapshot == s,
        "manifest_source",
    )
    require(
        (
            rubric.scenario_id,
            rubric.scenario_version,
            rubric.rubric_id,
            rubric.rubric_revision,
            rubric.content_digest,
        )
        == (
            s.scenario_id,
            s.scenario_version,
            value.source.rubric_id,
            s.rubric_revision,
            s.rubric_digest,
        ),
        "rubric_source",
    )
    require(
        fingerprint(parameters.model_dump(mode="json")) == s.scenario_digest
        and email_digest(email) == s.email_digest
        and fingerprint(web.model_dump(mode="json")) == s.web_digest
        and fingerprint(link.model_dump(mode="json")) == s.link_digest,
        "material_source_digest",
    )
    require(
        (
            link.scenario_id,
            link.scenario_version,
            link.revision,
            link.source_email_revision,
            link.source_email_digest,
            link.target_web_revision,
            link.target_web_digest,
            link.target_resource_id,
        )
        == (
            s.scenario_id,
            s.scenario_version,
            s.link_revision,
            s.email_revision,
            s.email_digest,
            s.web_revision,
            s.web_digest,
            web.page.internal_resource_id,
        ),
        "link_source",
    )
    require(
        (
            web.scenario_id,
            web.scenario_version,
            web.email_binding.revision,
            web.email_binding.digest,
        )
        == (s.scenario_id, s.scenario_version, s.email_revision, s.email_digest),
        "web_source",
    )
    expected = evidence_projection(value.attempt, value.events, rubric.criteria)
    require(
        expected
        == (value.path, value.transition, value.criteria, value.critical_observations),
        "selected_rubric_evidence",
    )
    pairs = {
        (c.id, a.id) for c in web.page.components for a in getattr(c, "actions", ())
    }
    for e in value.events:
        if e.surface == "web" and not e.component_id.startswith(BROWSER_PREFIX):
            require((e.component_id, e.action_id) in pairs, "authored_component")
        navigation = None
        if e.action_id == "started":
            expected_digest = fingerprint({"action": "started"})
        else:
            if e.action_id == "open_internal":
                navigation = InternalNavigationV1(
                    publication_id=value.source.publication_id,
                    scenario_id=s.scenario_id,
                    scenario_version=s.scenario_version,
                    internal_resource_id=web.page.internal_resource_id,
                    manifest_digest=manifest.manifest_digest,
                ).model_dump(mode="json")
            expected_digest = fingerprint(
                dict(
                    surface=e.surface,
                    action_id=e.action_id,
                    component_id=e.component_id,
                    navigation=navigation,
                    source_message_identifier="main" if navigation else None,
                )
            )
        require(e.operation_digest == expected_digest, "operation_digest")
    validate_evidence_structure(value)


def validate_result_against_evidence(result, evidence, *, details=None):
    """Read-only envelope/detail/evidence consistency, no repair or rescoring."""
    from .contracts import (
        CriterionEvaluationV1,
        EvaluationEvidenceV1,
        EvaluationResultV1,
    )

    evidence = EvaluationEvidenceV1.model_validate_json(canonical_bytes(evidence))
    result = EvaluationResultV1.model_validate_json(canonical_bytes(result))
    for name in (
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
    ):
        require(
            getattr(result, name) == getattr(evidence, name),
            "stored_evaluation_binding",
        )
    require(len(result.criteria) == len(evidence.criteria), "criterion_completeness")
    for stored, factual in zip(result.criteria, evidence.criteria, strict=True):
        require(
            stored.criterion == factual.criterion
            and stored.applicable == factual.applicable
            and stored.supporting_event_refs == factual.supporting_event_refs,
            "criterion_evidence_binding",
        )
    if details is not None:
        parsed = tuple(
            CriterionEvaluationV1.model_validate_json(canonical_bytes(d))
            for d in details
        )
        require(parsed == result.criteria, "stored_criterion_rows")
    return result


def validate_stored_projection(result, evidence, *, details, **sources):
    """Single pure integrity entry; caller owns transactional authorization/reads."""
    from .contracts import EvaluationEvidenceV1

    evidence = EvaluationEvidenceV1.model_validate_json(canonical_bytes(evidence))
    validate_sources(evidence, **sources)
    return validate_result_against_evidence(result, evidence, details=details)
