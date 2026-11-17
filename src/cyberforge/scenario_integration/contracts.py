"""Closed publication contracts and a bounded declarative criterion registry."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from cyberforge.agents.contracts import resource_id
from cyberforge.llm.contracts import Contract
from cyberforge.web.contracts import display_address, fingerprint, text_data

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[int, Field(strict=True, ge=1)]
Applicability = Literal["all_attempts", "web_visited", "web_not_visited"]
Phase = Literal["email", "transition", "web"]


class Definition(Contract):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ScenarioLinkV1(Definition):
    schema_version: Literal["scenario-link-v1"] = "scenario-link-v1"
    scenario_id: Identifier
    scenario_version: Identifier
    revision: Identifier
    source_email_revision: Identifier
    source_email_digest: Digest
    source_message_identifier: Literal["main"] = "main"
    target_web_revision: Identifier
    target_web_digest: Digest
    link_label: str = Field(min_length=1, max_length=200)
    display_url: str = Field(max_length=512)
    target_resource_id: str
    allowed_action: Literal["open_internal"] = "open_internal"
    linkage_provenance: Digest

    @model_validator(mode="after")
    def safe(self) -> Self:
        text_data(self.link_label, limit=200)
        display_address(self.display_url)
        resource_id(self.target_resource_id)
        return self


@dataclass(frozen=True)
class CriterionSpec:
    id: str
    label: str
    description: str
    phase: Phase
    actions: tuple[str, ...]
    applicability: tuple[Applicability, ...]


# IDs and meanings are versioned as a unit. Extension requires a new registry
# version; historical definitions must never acquire different meanings.
CRITERIA = (
    CriterionSpec(
        "email.sender",
        "Перевірка відправника",
        "Огляд відправника листа.",
        "email",
        ("inspect_sender",),
        ("all_attempts",),
    ),
    CriterionSpec(
        "email.link",
        "Перевірка посилання",
        "Огляд навчального посилання.",
        "email",
        ("inspect_link",),
        ("all_attempts",),
    ),
    CriterionSpec(
        "email.report",
        "Повідомлення про лист",
        "Повідомлення про підозрілий лист.",
        "email",
        ("report",),
        ("all_attempts",),
    ),
    CriterionSpec(
        "transition.safe_decline",
        "Безпечна відмова",
        "Відмова від підозрілого переходу є успішним шляхом.",
        "transition",
        ("decline",),
        ("all_attempts", "web_not_visited"),
    ),
    CriterionSpec(
        "transition.decision",
        "Рішення про перехід",
        "Перевірка рішення за навчальною метою викладача; без числового результату.",
        "transition",
        ("decline", "open_internal"),
        ("all_attempts",),
    ),
    CriterionSpec(
        "web.address",
        "Перевірка адреси сайту",
        "Огляд відображуваної адреси.",
        "web",
        ("inspect_address",),
        ("web_visited",),
    ),
    CriterionSpec(
        "web.leave",
        "Безпечний вихід",
        "Вихід із підозрілої сторінки.",
        "web",
        ("leave",),
        ("web_visited",),
    ),
    CriterionSpec(
        "web.report",
        "Повідомлення про сайт",
        "Повідомлення про підозрілий сайт.",
        "web",
        ("report",),
        ("web_visited",),
    ),
)
REGISTRY = {criterion.id: criterion for criterion in CRITERIA}


class RubricCriterionV1(Definition):
    criterion_id: str
    label: str
    description: str
    phase: Phase
    weight: float = Field(gt=0, le=10000, allow_inf_nan=False, strict=True)
    applicability: Applicability
    evidence_actions: tuple[str, ...]
    # Critical numeric semantics are unapproved; this version declares none.
    critical_action: Literal[None] = None

    @model_validator(mode="after")
    def registered(self) -> Self:
        spec = REGISTRY.get(self.criterion_id)
        if spec is None or (
            (self.label, self.description, self.phase, self.evidence_actions)
            != (spec.label, spec.description, spec.phase, spec.actions)
            or self.applicability not in spec.applicability
        ):
            raise ValueError("unsupported_criterion_or_evidence")
        return self


def criterion(
    identifier: str, weight: float = 1.0, applicability: Applicability | None = None
) -> RubricCriterionV1:
    spec = REGISTRY[identifier]
    return RubricCriterionV1(
        criterion_id=spec.id,
        label=spec.label,
        description=spec.description,
        phase=spec.phase,
        evidence_actions=spec.actions,
        weight=weight,
        applicability=applicability or spec.applicability[0],
    )


class RubricDefinitionV1(Definition):
    rubric_schema_version: Literal["rubric-definition-v1"] = "rubric-definition-v1"
    registry_version: Literal["criterion-registry-v1"] = "criterion-registry-v1"
    # A declaration, NOT an implemented scoring algorithm.
    semantics_version: Literal["rubric-declarations-v1"] = "rubric-declarations-v1"
    rubric_id: str
    rubric_revision: Identifier
    scenario_id: Identifier
    scenario_version: Identifier
    criteria: tuple[RubricCriterionV1, ...] = Field(min_length=1, max_length=24)
    author_id: Identifier
    saved_at: datetime
    content_digest: Digest

    def content(self) -> dict:
        return self.model_dump(mode="json", exclude={"content_digest"})

    @model_validator(mode="after")
    def usable(self) -> Self:
        ids = [c.criterion_id for c in self.criteria]
        if len(set(ids)) != len(ids) or not any(
            c.phase != "web" and c.applicability != "web_visited" for c in self.criteria
        ):
            raise ValueError("duplicate_or_no_safe_path_criterion")
        resource_id(self.rubric_id)
        if self.content_digest != fingerprint(self.content()):
            raise ValueError("rubric_digest")
        return self


class ReviewedSourcesV1(Definition):
    scenario_id: Identifier
    scenario_version: Identifier
    scenario_revision: Identifier
    scenario_digest: Digest
    archive_revision: int = Field(strict=True, ge=0)
    email_revision: Identifier
    email_digest: Digest
    web_revision: Identifier
    web_digest: Digest
    link_revision: Identifier
    link_digest: Digest
    rubric_revision: Identifier
    rubric_digest: Digest


class ReadinessCheckV1(Definition):
    check_id: str
    status: Literal["PASS", "WARNING", "BLOCKED"]
    explanation: str
    correction: str


class ScenarioReadinessReportV1(Definition):
    schema_version: Literal["scenario-readiness-v1"] = "scenario-readiness-v1"
    scenario_id: Identifier
    scenario_version: Identifier
    # Available even when a corrupt/missing source prevents a complete snapshot.
    checked_sources: dict[str, int | str | None]
    snapshot: ReviewedSourcesV1 | None
    checks: tuple[ReadinessCheckV1, ...]
    technical_ready: bool
    final_ready: bool
    acknowledgement_requirements: tuple[str, ...]
    selected_group_ids: tuple[int, ...]
    review_fingerprint: Digest | None


class InstructorConfirmationV1(Definition):
    schema_version: Literal["instructor-confirmation-v1"] = "instructor-confirmation-v1"
    confirmation_id: str
    actor_id: Identifier
    confirmed_at: datetime
    review_fingerprint: Digest
    snapshot: ReviewedSourcesV1
    selected_group_ids: tuple[int, ...] = Field(min_length=1)
    acknowledged_warnings: tuple[str, ...]
    semantic_review: Literal[True]


class ScenarioPublicationManifestV1(Definition):
    schema_version: Literal["scenario-publication-v1"] = "scenario-publication-v1"
    snapshot: ReviewedSourcesV1
    email_schema: Literal["email-draft-v2"] = "email-draft-v2"
    web_schema: Literal["web-draft-v3"] = "web-draft-v3"
    web_renderer: Literal["web-renderer-v1"] = "web-renderer-v1"
    link_schema: Literal["scenario-link-v1"] = "scenario-link-v1"
    rubric_schema: Literal["rubric-definition-v1"] = "rubric-definition-v1"
    rubric_semantics: Literal["rubric-declarations-v1"] = "rubric-declarations-v1"
    email_renderer: Literal["native-email-v1"] = "native-email-v1"
    publisher_id: Identifier
    published_at: datetime
    confirmation_id: str
    manifest_digest: Digest

    @model_validator(mode="after")
    def digest_matches(self) -> Self:
        if self.manifest_digest != fingerprint(
            self.model_dump(mode="json", exclude={"manifest_digest"})
        ):
            raise ValueError("manifest_digest")
        return self


class InternalNavigationV1(Definition):
    schema_version: Literal["internal-navigation-v1"] = "internal-navigation-v1"
    publication_id: Identifier
    scenario_id: Identifier
    scenario_version: Identifier
    source_message_identifier: Literal["main"] = "main"
    allowed_action: Literal["open_internal"] = "open_internal"
    internal_resource_id: str
    manifest_digest: Digest
