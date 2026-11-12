"""Transactional scenario management; UI and future generators share this boundary."""

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.domain.scenarios import (
    Scenario,
    ScenarioParameters,
    ScenarioStatus,
    stored_parameters,
)
from cyberforge.persistence.models import ScenarioRecord, ScenarioVersion, User


class ScenarioService:
    def __init__(self, accounts: AccountService) -> None:
        self.accounts = accounts

    def _record(
        self, db: Session, actor: User, scenario_id: int, *, write: bool = False
    ) -> ScenarioRecord:
        record = db.get(ScenarioRecord, scenario_id)
        if record is None or (
            record.owner_id != actor.id and (write or actor.role != Role.ADMINISTRATOR)
        ):
            # Unknown and inaccessible IDs have the same response.
            raise AccessDenied()
        return record

    @staticmethod
    def _latest(db: Session, scenario_id: int) -> ScenarioVersion:
        version = db.scalar(
            select(ScenarioVersion)
            .where(ScenarioVersion.scenario_id == scenario_id)
            .order_by(ScenarioVersion.number.desc())
            .limit(1)
        )
        if version is None:
            raise ApplicationError("Версію сценарію не знайдено.")
        return version

    @staticmethod
    def _value(record: ScenarioRecord, version: ScenarioVersion) -> Scenario:
        try:
            parameters = stored_parameters(version.parameters)
        except (ValidationError, ValueError, TypeError):
            raise ApplicationError(
                "Збережені параметри сценарію не підтримуються або пошкоджені. "
                "Дані не змінено."
            ) from None
        return Scenario(
            id=record.id,
            owner_id=record.owner_id,
            created_at=record.created_at.replace(tzinfo=UTC),
            archived_at=record.archived_at.replace(tzinfo=UTC)
            if record.archived_at
            else None,
            archive_revision=record.archive_revision,
            version=version.number,
            revision=version.revision,
            version_created_at=version.created_at.replace(tzinfo=UTC),
            updated_at=version.updated_at.replace(tzinfo=UTC),
            status=ScenarioStatus(version.status),
            parameters=parameters,
        )

    @staticmethod
    def _parameters(parameters: ScenarioParameters | dict) -> dict:
        try:
            # Revalidate even an existing model (including nested mutable JSON).
            source = (
                parameters.model_dump(mode="python")
                if isinstance(parameters, ScenarioParameters)
                else parameters
            )
            return ScenarioParameters.model_validate(source).bounded_payload()
        except (ValidationError, ValueError):
            raise ApplicationError(
                "Некоректні параметри: тема обов’язкова (до 2000 символів); "
                "виберіть складність. Аудиторія — до 1000, опис і мета — до "
                "10000, кожна тактика/ознака — до 200 символів (до 100 записів). "
                "Додаткові параметри — JSON-об’єкт; загалом до 50 000 символів."
                " Ознаки NIST обирайте за ідентифікаторами перевіреного каталогу."
            ) from None

    def create(
        self, token: str | None, parameters: ScenarioParameters | dict
    ) -> Scenario:
        with self.accounts.transaction(write=True) as db:
            actor = self.accounts.require(
                db, token, Role.ADMINISTRATOR, Role.INSTRUCTOR
            )
            payload = self._parameters(parameters)
            if payload["legacy_nist_cues"]:
                raise ApplicationError(
                    "Власні тактики вводьте окремо від офіційних ознак NIST."
                )
            now = datetime.now(UTC).replace(tzinfo=None)
            record = ScenarioRecord(owner_id=actor.id, created_at=now)
            db.add(record)
            db.flush()
            version = ScenarioVersion(
                scenario_id=record.id,
                number=1,
                revision=1,
                status=ScenarioStatus.DRAFT,
                parameters=payload,
                created_at=now,
                updated_at=now,
            )
            db.add(version)
            db.flush()
            return self._value(record, version)

    def get(
        self, token: str | None, scenario_id: int, *, version: int | None = None
    ) -> Scenario:
        with self.accounts.transaction() as db:
            actor = self.accounts.require(
                db, token, Role.ADMINISTRATOR, Role.INSTRUCTOR
            )
            record = self._record(db, actor, scenario_id)
            row = (
                self._latest(db, scenario_id)
                if version is None
                else db.scalar(
                    select(ScenarioVersion).where(
                        ScenarioVersion.scenario_id == scenario_id,
                        ScenarioVersion.number == version,
                    )
                )
            )
            if row is None:
                raise ApplicationError("Версію сценарію не знайдено.")
            return self._value(record, row)

    def catalog(
        self, token: str | None, *, archived: bool | None = False
    ) -> tuple[Scenario, ...]:
        with self.accounts.transaction() as db:
            actor = self.accounts.require(
                db, token, Role.ADMINISTRATOR, Role.INSTRUCTOR
            )
            latest = (
                select(
                    ScenarioVersion.scenario_id,
                    func.max(ScenarioVersion.number).label("number"),
                )
                .group_by(ScenarioVersion.scenario_id)
                .subquery()
            )
            query = (
                select(ScenarioRecord, ScenarioVersion)
                .join(ScenarioVersion, ScenarioVersion.scenario_id == ScenarioRecord.id)
                .join(
                    latest,
                    (latest.c.scenario_id == ScenarioRecord.id)
                    & (latest.c.number == ScenarioVersion.number),
                )
                .order_by(ScenarioRecord.id.desc())
            )
            if actor.role != Role.ADMINISTRATOR:
                query = query.where(ScenarioRecord.owner_id == actor.id)
            if archived is not None:
                query = query.where(
                    ScenarioRecord.archived_at.is_not(None)
                    if archived
                    else ScenarioRecord.archived_at.is_(None)
                )
            return tuple(self._value(record, row) for record, row in db.execute(query))

    def update(
        self,
        token: str | None,
        scenario_id: int,
        parameters: ScenarioParameters | dict,
        *,
        expected_version: int,
        expected_revision: int,
        expected_archive_revision: int = 0,
    ) -> Scenario:
        with self.accounts.transaction(write=True) as db:
            actor = self.accounts.require(
                db, token, Role.ADMINISTRATOR, Role.INSTRUCTOR
            )
            record = self._record(db, actor, scenario_id, write=True)
            if record.archived_at is not None:
                raise ApplicationError(
                    "Сценарій архівовано. Відновіть його перед редагуванням."
                )
            row = self._latest(db, scenario_id)
            if (row.number, row.revision, record.archive_revision) != (
                expected_version,
                expected_revision,
                expected_archive_revision,
            ):
                raise ApplicationError(
                    "Сценарій уже змінено. Ваші правки збережено у формі. "
                    "Скопіюйте їх і повторно відкрийте актуальну версію."
                )
            payload = self._parameters(parameters)
            previous = self._value(record, row).parameters
            if tuple(payload["legacy_nist_cues"]) != previous.legacy_nist_cues:
                raise ApplicationError(
                    "Збережені некласифіковані ознаки не можна змінювати або видаляти."
                )
            if payload == previous.model_dump(mode="json"):
                return self._value(record, row)
            now = datetime.now(UTC).replace(tzinfo=None)
            if row.status == ScenarioStatus.PUBLISHED:
                # Publishing itself belongs to Phase 8. Never mutate its snapshot.
                row = ScenarioVersion(
                    scenario_id=record.id,
                    number=row.number + 1,
                    revision=1,
                    status=ScenarioStatus.DRAFT,
                    parameters=payload,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            else:
                row.parameters = payload
                row.revision += 1
                row.updated_at = now
            db.flush()
            return self._value(record, row)

    def _archive_state(
        self,
        token: str | None,
        scenario_id: int,
        *,
        archived: bool,
        expected_version: int,
        expected_revision: int,
        expected_archive_revision: int,
    ) -> Scenario:
        with self.accounts.transaction(write=True) as db:
            actor = self.accounts.require(
                db, token, Role.ADMINISTRATOR, Role.INSTRUCTOR
            )
            record = self._record(db, actor, scenario_id, write=True)
            row = self._latest(db, scenario_id)
            if (row.number, row.revision, record.archive_revision) != (
                expected_version,
                expected_revision,
                expected_archive_revision,
            ):
                raise ApplicationError(
                    "Сценарій уже змінено. Повторно відкрийте його картку."
                )
            if (record.archived_at is not None) != archived:
                record.archived_at = (
                    datetime.now(UTC).replace(tzinfo=None) if archived else None
                )
                record.archive_revision += 1
                db.flush()
            return self._value(record, row)

    def archive(
        self,
        token: str | None,
        scenario_id: int,
        *,
        expected_version: int,
        expected_revision: int,
        expected_archive_revision: int,
    ) -> Scenario:
        return self._archive_state(
            token,
            scenario_id,
            archived=True,
            expected_version=expected_version,
            expected_revision=expected_revision,
            expected_archive_revision=expected_archive_revision,
        )

    def restore(
        self,
        token: str | None,
        scenario_id: int,
        *,
        expected_version: int,
        expected_revision: int,
        expected_archive_revision: int,
    ) -> Scenario:
        return self._archive_state(
            token,
            scenario_id,
            archived=False,
            expected_version=expected_version,
            expected_revision=expected_revision,
            expected_archive_revision=expected_archive_revision,
        )
