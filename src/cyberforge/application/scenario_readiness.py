"""Derived readiness and exact instructor attestations, never a permanent READY flag."""

from datetime import UTC, datetime
from uuid import uuid4

from cyberforge.application.scenario_integration import (
    INVALID,
    ScenarioIntegrationService,
    check,
    decoded,
)
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.domain.scenarios import Scenario, ScenarioStatus
from cyberforge.persistence.models import (
    Group,
    GroupInstructor,
    PublicationReview,
)
from cyberforge.scenario_integration.contracts import (
    InstructorConfirmationV1,
    ScenarioReadinessReportV1,
)
from cyberforge.web.contracts import fingerprint


def group_ids(values) -> tuple[int, ...]:
    if (
        not isinstance(values, (tuple, list))
        or any(type(value) is not int or value < 1 for value in values)
        or len(values) != len(set(values))
    ):
        raise ApplicationError("Оберіть унікальні ідентифікатори навчальних груп.")
    return tuple(sorted(values))


def authorized_groups(db, actor, identifiers) -> bool:
    for identifier in identifiers:
        if db.get(Group, identifier) is None or (
            actor.role != Role.ADMINISTRATOR
            and db.get(GroupInstructor, (identifier, actor.id)) is None
        ):
            return False
    return True


class ScenarioReadinessService:
    def __init__(self, integration: ScenarioIntegrationService):
        self.integration = integration
        self.accounts = integration.accounts

    def evaluate(
        self, token, expected: Scenario, *, selected_group_ids=(), confirmation_id=None
    ):
        with self.accounts.transaction() as db:
            return self._evaluate(
                db,
                token,
                expected,
                selected_group_ids=selected_group_ids,
                confirmation_id=confirmation_id,
            )[0]

    def _evaluate(
        self, db, token, expected, *, selected_group_ids=(), confirmation_id=None
    ):
        state = self.integration._load(db, token, expected)
        actor = self.accounts.require(db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR)
        groups = group_ids(selected_group_ids)
        current = state.scenario
        active = not current.archived and current.status == ScenarioStatus.DRAFT
        latest = self.integration.scenarios._latest(db, current.id)
        checks = [
            check(
                "active_draft",
                active and latest.number == current.version,
                "Активна поточна чернетка.",
                "Сценарій архівовано, версію вже опубліковано або відкрито "
                "історичну версію. Відкрийте актуальну чернетку.",
            ),
            *state.checks,
        ]
        technical_ready = not any(c.status == "BLOCKED" for c in checks)
        warnings = tuple(c.check_id for c in checks if c.status == "WARNING")
        review_fingerprint = (
            fingerprint(
                dict(
                    snapshot=state.snapshot.model_dump(mode="json"),
                    groups=groups,
                    warnings=warnings,
                )
            )
            if state.snapshot
            else None
        )
        groups_valid = bool(groups) and authorized_groups(db, actor, groups)
        checks.append(
            check(
                "groups",
                groups_valid,
                "Вибрані навчальні групи дозволені.",
                "Оберіть хоча б одну доступну вам навчальну групу.",
            )
        )
        confirmation = (
            db.get(PublicationReview, confirmation_id) if confirmation_id else None
        )
        reviewed = False
        if confirmation is not None:
            try:
                receipt = decoded(InstructorConfirmationV1, confirmation.payload)
                reviewed = (
                    confirmation.version_id == state.version_id
                    and confirmation.actor_id == actor.id == receipt.actor_id
                    and receipt.confirmation_id == confirmation.id
                    and receipt.review_fingerprint == review_fingerprint
                    and receipt.snapshot == state.snapshot
                    and receipt.selected_group_ids == groups
                    and receipt.acknowledged_warnings == warnings
                    and receipt.semantic_review is True
                )
            except INVALID:
                pass
        checks.append(
            check(
                "instructor_confirmation",
                reviewed,
                "Викладач підтвердив точні ревізії, попередження та групи.",
                "Підтвердіть публікацію актуального знімка. Попереднє "
                "підтвердження після змін недійсне.",
            )
        )
        return ScenarioReadinessReportV1(
            scenario_id=current.id,
            scenario_version=current.version,
            checked_sources=state.checked_sources,
            snapshot=state.snapshot,
            checks=tuple(checks),
            technical_ready=technical_ready,
            final_ready=technical_ready and groups_valid and reviewed,
            acknowledgement_requirements=warnings,
            selected_group_ids=groups,
            review_fingerprint=review_fingerprint,
        ), state

    def confirm(
        self,
        token,
        expected: Scenario,
        *,
        review_fingerprint: str,
        selected_group_ids,
        acknowledged_warnings,
        semantic_review: bool,
    ):
        with self.accounts.transaction(write=True) as db:
            # Require owner/latest draft even if an administrator could inspect it.
            self.integration.emails._current(db, token, expected, write=True)
            report, state = self._evaluate(
                db, token, expected, selected_group_ids=selected_group_ids
            )
            actor = self.accounts.require(
                db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR
            )
            # Validate publication inputs explicitly before constructing the strict
            # receipt; technical readiness intentionally excludes group selection.
            if not report.selected_group_ids:
                raise ApplicationError("Оберіть хоча б одну навчальну групу.")
            if not authorized_groups(db, actor, report.selected_group_ids):
                raise ApplicationError(
                    "Доступ до вибраних груп відсутній або змінився. "
                    "Оновіть список навчальних груп."
                )
            if (
                not report.technical_ready
                or not report.snapshot
                or any(
                    c.status == "BLOCKED" and c.check_id != "instructor_confirmation"
                    for c in report.checks
                )
            ):
                raise ApplicationError(
                    "Сценарій має блокувальні помилки або немає дозволених груп."
                )
            if report.review_fingerprint != review_fingerprint:
                raise ApplicationError(
                    "Дані огляду змінилися. Перевірте готовність повторно."
                )
            if (
                semantic_review is not True
                or tuple(acknowledged_warnings) != report.acknowledgement_requirements
            ):
                raise ApplicationError(
                    "Потрібне явне підтвердження змісту та всіх попереджень."
                )
            receipt = InstructorConfirmationV1(
                confirmation_id=uuid4().hex,
                actor_id=actor.id,
                confirmed_at=datetime.now(UTC),
                review_fingerprint=report.review_fingerprint,
                snapshot=report.snapshot,
                selected_group_ids=report.selected_group_ids,
                acknowledged_warnings=report.acknowledgement_requirements,
                semantic_review=True,
            )
            db.add(
                PublicationReview(
                    id=receipt.confirmation_id,
                    version_id=state.version_id,
                    actor_id=actor.id,
                    payload=receipt.model_dump(mode="json"),
                )
            )
            db.flush()
        return receipt
