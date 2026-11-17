"""Closed attempt state and factual event vocabulary, independent of scoring."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from cyberforge.scenario_integration.contracts import Definition, Digest, Identifier

Status = Literal["IN_PROGRESS", "COMPLETED", "ABANDONED"]
Stage = Literal["EMAIL", "WEB"]
Surface = Literal["email", "transition", "web", "system"]
Action = Literal[
    "started",
    "email_opened",
    "inspect_sender",
    "inspect_link",
    "report",
    "decline",
    "open_internal",
    "web_entered",
    "inspect_address",
    "leave",
    "confirm",
    "submit_synthetic",
    "completed",
    "abandoned",
]
ACTIONS = {
    "email": frozenset({"email_opened", "inspect_sender", "inspect_link", "report"}),
    "transition": frozenset({"decline", "open_internal"}),
    "web": frozenset(
        {"inspect_address", "leave", "report", "confirm", "submit_synthetic"}
    ),
    "system": frozenset({"started", "web_entered", "completed", "abandoned"}),
}


class ScenarioAttemptV1(Definition):
    schema_version: Literal["scenario-attempt-v1"] = "scenario-attempt-v1"
    attempt_id: UUID
    learner_id: Identifier
    publication_id: Identifier
    scenario_id: Identifier
    scenario_version: Identifier
    manifest_digest: Digest
    authorization_group_id: Identifier
    scenario_name: str = Field(min_length=1, max_length=200)
    status: Status
    current_stage: Stage
    email_opened: bool
    decision: Literal["NONE", "DECLINED", "LEFT"]
    web_visited: bool
    started_at: AwareDatetime
    completed_at: AwareDatetime | None
    abandoned_at: AwareDatetime | None
    revision: Identifier
    last_event_sequence: Annotated[int, Field(strict=True, ge=0)]

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if (self.status == "COMPLETED") != (self.completed_at is not None):
            raise ValueError("completion timestamp")
        if (self.status == "ABANDONED") != (self.abandoned_at is not None):
            raise ValueError("abandonment timestamp")
        for stamp in (self.completed_at, self.abandoned_at):
            if stamp is not None and stamp < self.started_at:
                raise ValueError("timestamp order")
        if self.current_stage == "EMAIL" and self.web_visited:
            raise ValueError("web stage")
        return self


class AttemptEventV1(Definition):
    schema_version: Literal["attempt-event-v1"] = "attempt-event-v1"
    event_id: UUID
    attempt_id: UUID
    sequence: Identifier
    surface: Surface
    action_id: Action
    component_id: str | None = Field(default=None, min_length=1, max_length=80)
    timestamp: AwareDatetime
    request_id: UUID
    operation_digest: Digest
    operation_index: Annotated[int, Field(strict=True, ge=0, le=2)]

    @model_validator(mode="after")
    def vocabulary(self) -> Self:
        if self.action_id not in ACTIONS[self.surface]:
            raise ValueError("action surface")
        if (self.surface == "web") != (self.component_id is not None):
            raise ValueError("component surface")
        return self


def utc(value: datetime | None):
    """SQLite stores UTC without tzinfo, restored at the persistence boundary."""
    from datetime import UTC

    return value.replace(tzinfo=UTC) if value is not None else None
