"""Specialized draft generation; callers own authorization and persistence."""

from cyberforge.agents.specialized import (
    AssistantAgent,
    EmailScenarioAgent,
    MentorAgent,
    WebScenarioAgent,
)

__all__ = ["AssistantAgent", "EmailScenarioAgent", "MentorAgent", "WebScenarioAgent"]
