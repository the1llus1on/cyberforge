"""Phase 5 drafts: closed provider slots and mandatory local validation.

Bounds are model validators deliberately absent from provider JSON Schema. This
keeps the accepted Groq subset intact; the gateway always validates locally.
"""

import json
import re
from hashlib import sha256
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, model_validator

from cyberforge.domain.nist_cues import NistCueId
from cyberforge.domain.scenarios import ScenarioParameters
from cyberforge.llm.contracts import (
    Contract,
    EmailArtifactV1,
    ErrorCategory,
    GenerationError,
    ScenarioContextV1,
    WebArtifactV1,
)

Action = Literal["inspect_sender", "inspect_link", "report", "decline", "open_internal"]
WebAction = Literal["inspect_address", "leave", "submit_synthetic", "report"]
Template = Literal["login", "portal", "notice", "document"]
Topic = Literal[
    "sender_verification", "link_inspection", "reporting", "data_protection"
]


def safe_text(value: str) -> None:
    if not value.strip() or len(value) > 4000:
        raise ValueError("text_bounds")
    if re.search(
        r"[<>\x00-\x08\x0b\x0c\x0e-\x1f]|javascript:|data:|file:|"
        r"\b(?:sk-|gsk_)[a-zA-Z0-9_-]{12,}|AIza[a-zA-Z0-9_-]{20,}|"
        r"(?:api[_ -]?key|password|token)\s*[=:]\s*\S+|\$\(|```|"
        r"\b(?:eval|exec|os\.system|subprocess\.\w+)\s*\(|"
        r"\b(?:powershell|cmd\.exe|curl|wget)\b|#!/(?:bin|usr)/",
        value,
        re.I,
    ):
        raise ValueError("unsafe_content")
    for address in re.findall(r"[\w.+-]+@([\w.-]+)", value):
        if not address.endswith(".invalid"):
            raise ValueError("non_synthetic_address")
    for url in re.findall(r"https?://[^\s]+", value):
        parsed = urlsplit(url)
        if not (parsed.hostname or "").endswith(".invalid"):
            raise ValueError("external_reference")


def resource_id(value: str) -> None:
    if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value) is None:
        raise ValueError("resource_id")


class Slots(Contract):
    """Strict closed slots. Every value is also bounded locally after generation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        strict=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def bounded(self) -> Self:
        def check(value):
            if isinstance(value, str):
                safe_text(value)
            elif isinstance(value, list):
                if len(value) > 24:
                    raise ValueError("list_bounds")
                for item in value:
                    check(item)
            elif isinstance(value, dict):
                for item in value.values():
                    check(item)

        payload = self.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False)) > 18000:
            raise ValueError("payload_bounds")
        try:
            check(payload)
        except ValueError as exc:
            if str(exc) in {
                "unsafe_content",
                "non_synthetic_address",
                "external_reference",
            }:
                raise GenerationError(ErrorCategory.SAFETY) from None
            raise
        return self


class MessageV1(Slots):
    sender_name: str
    sender_address: str
    subject: str
    body_text: str

    @model_validator(mode="after")
    def address(self) -> Self:
        if (
            re.fullmatch(
                r"[a-zA-Z0-9._+-]{1,64}@[a-z0-9-]+\.invalid", self.sender_address
            )
            is None
        ):
            raise ValueError("synthetic_sender")
        return self


class EmailSlotsV1(Slots):
    schema_version: Literal["email-slots-v1"]
    context_token: str
    internal_resource_id: str
    main: MessageV1
    background: list[MessageV1]
    indicators: list[str]
    claimed_cues: list[NistCueId]
    expected_actions: list[Action]

    @model_validator(mode="after")
    def email_rules(self) -> Self:
        resource_id(self.internal_resource_id)
        if not 1 <= len(self.background) <= 8 or not self.expected_actions:
            raise ValueError("email_structure")
        if len(set(self.claimed_cues)) != len(self.claimed_cues):
            raise ValueError("duplicate_cues")
        return self


class FormFieldV1(Slots):
    field_id: Literal["synthetic_login", "synthetic_code", "synthetic_confirmation"]
    label: str
    kind: Literal["synthetic_text", "confirmation"]
    # No value/default/password or submission endpoint is generated.


class WebSlotsV1(Slots):
    schema_version: Literal["web-slots-v1"]
    context_token: str
    internal_resource_id: str
    template: Template
    tab_title: str
    display_url: str
    heading: str
    body_text: str
    button_labels: list[str]
    fields: list[FormFieldV1]
    instructions: list[str]
    allowed_actions: list[WebAction]
    educational_cues: list[str]

    @model_validator(mode="after")
    def web_rules(self) -> Self:
        resource_id(self.internal_resource_id)
        url = urlsplit(self.display_url)
        if (
            url.scheme != "https"
            or not (url.hostname or "").endswith(".invalid")
            or url.username
            or url.password
            or url.port
            or url.query
            or url.fragment
        ):
            raise ValueError("display_only_address")
        if not self.button_labels or not self.allowed_actions or len(self.fields) > 3:
            raise ValueError("web_structure")
        if len({f.field_id for f in self.fields}) != len(self.fields):
            raise ValueError("duplicate_fields")
        return self


class ScenarioInputV1(Contract):
    schema_version: Literal["scenario-agent-input-v1"] = "scenario-agent-input-v1"
    synthetic: Literal[True]
    # Metadata only: never authorizes access or triggers database retrieval.
    scenario_id: int | None = Field(default=None, ge=1)
    scenario_version: int | None = Field(default=None, ge=1)
    parameters: ScenarioParameters
    context: ScenarioContextV1
    language: Literal["uk", "en"] = "uk"
    refinement: str | None = Field(default=None, max_length=2000, repr=False)

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        self.parameters.bounded_payload()
        resource_id(self.context.internal_resource_id)
        # Exclude arbitrary generation_parameters from cloud-bound projection.
        for text in (
            self.parameters.topic,
            self.parameters.audience,
            self.parameters.description,
            self.parameters.learning_objective,
            *self.parameters.tactics,
            self.context.organization,
            self.context.sender_name,
            self.context.premise,
            self.refinement,
        ):
            if text:
                safe_text(text)
        if len(self.context.model_dump_json()) > 6000:
            raise ValueError("context_bounds")
        return self


class EmailInputV1(ScenarioInputV1):
    previous: "EmailDraftV2 | EmailSlotsV1 | None" = Field(default=None, repr=False)

    @model_validator(mode="after")
    def previous_linkage(self) -> Self:
        if self.previous is not None:
            if (
                self.scenario_id is None
                or self.scenario_version is None
                or not isinstance(self.previous, EmailDraftV2)
                or self.previous.provenance != source_provenance(self)
            ):
                raise ValueError("previous_email_provenance")
        return self


class WebInputV1(ScenarioInputV1):
    email: "EmailDraftV2"
    template: Template
    previous: "WebDraftV2 | WebSlotsV1 | None" = Field(default=None, repr=False)

    @model_validator(mode="after")
    def linkage(self) -> Self:
        if (
            self.scenario_id is None
            or self.scenario_version is None
            or self.email.artifact.context != self.context
            or self.email.scenario_id != self.scenario_id
            or self.email.scenario_version != self.scenario_version
            or self.email.parameters != self.parameters
            or self.email.provenance != source_provenance(self)
            or (
                self.previous is not None
                and (
                    not isinstance(self.previous, WebDraftV2)
                    or self.previous.scenario_id != self.scenario_id
                    or self.previous.scenario_version != self.scenario_version
                    or self.previous.artifact.context != self.context
                    or self.previous.slots.template != self.template
                    or self.previous.provenance != source_provenance(self, web=True)
                )
            )
        ):
            raise ValueError("email_web_context")
        return self


class DraftProvenanceV1(Contract):
    """Local consistency fingerprint, never a signature or access permission."""

    schema_version: Literal["draft-provenance-v1"] = "draft-provenance-v1"
    kind: Literal["email", "web"]
    language: Literal["uk", "en"]
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def source_provenance(
    source: ScenarioInputV1, *, web: bool = False
) -> DraftProvenanceV1:
    """Stable source identity: excludes current refinement and previous draft.

    Web additionally binds associated Email content, excluding its request token.
    Keep all scenario parameters, even those excluded from cloud prompt data.
    """
    payload = {
        "scenario_id": source.scenario_id,
        "scenario_version": source.scenario_version,
        "parameters": source.parameters.model_dump(mode="json"),
        "context": source.context.model_dump(mode="json"),
        "language": source.language,
    }
    if web:
        payload["template"] = source.template
        email = source.email.model_dump(mode="json")
        # A changed Email refinement alone must not invalidate a Web draft.
        email["slots"].pop("context_token")
        payload["email"] = email
    return DraftProvenanceV1(
        kind="web" if web else "email",
        language=source.language,
        source_digest=sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    )


class EmailDraftV2(Contract):
    schema_version: Literal["email-draft-v2"] = "email-draft-v2"
    artifact: EmailArtifactV1
    slots: EmailSlotsV1
    parameters: ScenarioParameters
    scenario_id: int | None
    scenario_version: int | None
    # Additive local metadata: legacy envelopes remain readable, not reusable.
    provenance: DraftProvenanceV1 | None = None
    selected_cues: tuple[NistCueId, ...]
    # No semantic detector in Phase 5: claims NEVER become verified cues.
    verified_cues: tuple[NistCueId, ...] = ()
    cue_validation: Literal["requires_instructor_review"] = "requires_instructor_review"

    @model_validator(mode="after")
    def consistency(self) -> Self:
        if self.provenance is not None:
            expected = source_provenance(
                ScenarioInputV1(
                    synthetic=True,
                    scenario_id=self.scenario_id,
                    scenario_version=self.scenario_version,
                    parameters=self.parameters,
                    context=self.artifact.context,
                    language=self.provenance.language,
                )
            )
            if self.provenance != expected:
                raise ValueError("email_source_provenance")
        if (
            self.artifact.context.internal_resource_id
            != self.slots.internal_resource_id
            or self.artifact.subject != self.slots.main.subject
            or self.artifact.body_text != self.slots.main.body_text
            or self.artifact.context.sender_name != self.slots.main.sender_name
            or self.selected_cues != self.parameters.nist_cues
            or self.verified_cues
            or not set(self.slots.claimed_cues) <= set(self.selected_cues)
        ):
            raise ValueError("email_draft_consistency")
        return self


class WebDraftV2(Contract):
    schema_version: Literal["web-draft-v2"] = "web-draft-v2"
    artifact: WebArtifactV1
    slots: WebSlotsV1
    scenario_id: int | None
    scenario_version: int | None
    provenance: DraftProvenanceV1 | None = None

    @model_validator(mode="after")
    def consistency(self) -> Self:
        if (
            (self.provenance is not None and self.provenance.kind != "web")
            or self.artifact.context.internal_resource_id
            != self.slots.internal_resource_id
            or self.artifact.heading != self.slots.heading
            or self.artifact.body_text != self.slots.body_text
            or self.artifact.action_label != self.slots.button_labels[0]
        ):
            raise ValueError("web_draft_consistency")
        return self


class FactV1(Slots):
    """Trusted sanitized educational fact, not a raw event or learner record."""

    fact_id: str
    observation: str
    explanation: str
    defensive_behavior: str
    topic: Topic

    @model_validator(mode="after")
    def identifier(self) -> Self:
        resource_id(self.fact_id)
        return self


class ResultFactsV1(Contract):
    status: Literal["no_result", "incomplete", "completed"]
    score_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False, strict=True
    )
    rubric_version: str = Field(min_length=1, max_length=64)
    web_status: Literal["not_visited", "visited", "correctly_skipped"]

    @model_validator(mode="after")
    def result_rules(self) -> Self:
        safe_text(self.rubric_version)
        if (self.status == "completed") != (self.score_percent is not None):
            raise ValueError("precomputed_result")
        if self.web_status == "correctly_skipped" and self.status != "completed":
            raise ValueError("completion_required")
        return self


class ExplanationInputV1(Contract):
    synthetic: Literal[True]
    objective: str = Field(min_length=1, max_length=2000)
    facts: tuple[FactV1, ...] = Field(max_length=24)
    permitted_topics: tuple[Topic, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def facts_rules(self) -> Self:
        safe_text(self.objective)
        if len({f.fact_id for f in self.facts}) != len(self.facts):
            raise ValueError("duplicate_facts")
        if any(f.topic not in self.permitted_topics for f in self.facts):
            raise ValueError("unapproved_topic")
        return self


class MentorInputV1(ExplanationInputV1):
    schema_version: Literal["mentor-input-v1"] = "mentor-input-v1"
    result: ResultFactsV1


class AggregateV1(Contract):
    attempts: int = Field(ge=0, le=1000000, strict=True)
    completed: int = Field(ge=0, le=1000000, strict=True)
    mean_score: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False, strict=True
    )
    previous_mean_score: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )

    @model_validator(mode="after")
    def aggregate_rules(self) -> Self:
        if self.completed > self.attempts or (
            self.completed == 0 and self.mean_score is not None
        ):
            raise ValueError("aggregate_evidence")
        return self


class AssistantInputV1(ExplanationInputV1):
    schema_version: Literal["assistant-input-v1"] = "assistant-input-v1"
    scenario_version: int = Field(ge=1)
    aggregate: AggregateV1


class ExplanationSelectionV1(Slots):
    """Model selects supplied evidence; it cannot author scores, metrics or claims."""

    schema_version: Literal["explanation-selection-v1"]
    fact_ids: list[str]
    recommended_topics: list[Topic]
    evidence: Literal["supplied_facts", "insufficient"]
    difficulty_suggestion: Literal["keep", "instructor_review"]


class ExplanationV1(Contract):
    schema_version: Literal["explanation-v1"] = "explanation-v1"
    selected_facts: tuple[FactV1, ...]
    recommendations: tuple[str, ...]
    limitations: tuple[str, ...]
    result: ResultFactsV1 | None = None
    aggregate: AggregateV1 | None = None
    difficulty_suggestion: Literal["keep", "instructor_review"]
    decision_maker: Literal["instructor"] = "instructor"


EmailInputV1.model_rebuild()
WebInputV1.model_rebuild()
