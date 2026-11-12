"""Validated scenario parameters shared by the catalog and future generators."""

import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
)

from cyberforge.domain.nist_cues import NistCueId

Topic = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]
Selection = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class Difficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @property
    def label(self) -> str:
        return {
            self.BEGINNER: "Початкова",
            self.INTERMEDIATE: "Середня",
            self.ADVANCED: "Висока",
        }[self]


class ScenarioStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"

    @property
    def label(self) -> str:
        return {self.DRAFT: "Чернетка", self.PUBLISHED: "Опубліковано"}[self]


class ScenarioParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    topic: Topic
    difficulty: Difficulty
    audience: ShortText = ""
    description: LongText = ""
    learning_objective: LongText = ""
    tactics: tuple[Selection, ...] = Field(default=(), max_length=100)
    nist_cue_catalog: Literal["nist-tn-2276:2023"] = "nist-tn-2276:2023"
    nist_cues: tuple[NistCueId, ...] = Field(default=(), max_length=23)
    # Unmapped baseline strings remain separate; never classify by display text.
    legacy_nist_cues: tuple[str, ...] = Field(default=(), max_length=100)
    generation_parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("nist_cues")
    @classmethod
    def unique_cues(cls, value: tuple[NistCueId, ...]) -> tuple[NistCueId, ...]:
        if len(set(value)) != len(value):
            raise ValueError("Повторні ознаки NIST заборонено.")
        return value

    def bounded_payload(self) -> dict:
        """Return an independent JSON payload; never executable configuration."""
        payload = self.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False)) > 50000:
            raise ValueError("Параметри сценарію перевищують 50 000 символів.")
        return payload


def stored_parameters(payload: dict) -> ScenarioParameters:
    """Adapt old snapshots only on read; never rewrite historical JSON."""
    source = dict(payload)
    if "nist_cue_catalog" not in source:
        source["legacy_nist_cues"] = tuple(source.get("legacy_nist_cues", ())) + tuple(
            source.pop("nist_cues", ())
        )
    return ScenarioParameters.model_validate(source)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int
    owner_id: int
    created_at: datetime
    archived_at: datetime | None = None
    archive_revision: int = 0
    version: int
    revision: int
    version_created_at: datetime
    updated_at: datetime
    status: ScenarioStatus
    parameters: ScenarioParameters

    @property
    def name(self) -> str:
        return f"Сценарій {self.id}"

    @property
    def archived(self) -> bool:
        return self.archived_at is not None
