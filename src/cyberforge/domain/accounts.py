"""Public identity and group values; credentials never cross this boundary."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    ADMINISTRATOR = "administrator"
    INSTRUCTOR = "instructor"
    LEARNER = "learner"

    @property
    def label(self) -> str:
        return {
            self.ADMINISTRATOR: "Адміністратор",
            self.INSTRUCTOR: "Викладач",
            self.LEARNER: "Учень",
        }[self]


class Workspace(StrEnum):
    CONSTRUCTOR = "constructor"
    ANALYTICS = "analytics"
    ADMIN = "admin"
    MY_SCENARIOS = "my_scenarios"
    MY_RESULTS = "my_results"


class ApplicationError(Exception):
    """Safe Ukrainian message suitable for presentation."""


class AccessDenied(ApplicationError):
    def __init__(self) -> None:
        super().__init__("Доступ заборонено. Увійдіть з відповідними правами.")


@dataclass(frozen=True)
class Account:
    id: int
    username: str
    display_name: str
    role: Role
    active: bool


@dataclass(frozen=True)
class LearningGroup:
    id: int
    name: str
    description: str
    instructors: tuple[int, ...]
    learners: tuple[int, ...]
