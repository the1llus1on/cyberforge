"""Atomic publication, audited access grants and authorized future learner reads."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from cyberforge.application.scenario_integration import INVALID, decoded
from cyberforge.application.scenario_readiness import (
    ScenarioReadinessService,
    authorized_groups,
)
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.domain.scenarios import Scenario, ScenarioStatus
from cyberforge.persistence.models import (
    GroupLearner,
    PublicationGrantAuditEvent,
    PublicationGroup,
    PublicationReview,
    ScenarioPublication,
    ScenarioRecord,
    ScenarioVersion,
)
from cyberforge.scenario_integration.contracts import (
    InternalNavigationV1,
    ScenarioPublicationManifestV1,
)
from cyberforge.web.contracts import fingerprint


@dataclass(frozen=True)
class Publication:
    id: int
    manifest: ScenarioPublicationManifestV1


@dataclass(frozen=True)
class GroupGrant:
    group_id: int
    active: bool
    revision: int


@dataclass(frozen=True)
class GrantAuditEvent:
    id: int
    publication_id: int
    group_id: int
    actor_id: int
    operation: str
    occurred_at: datetime
    previous_active: bool
    new_active: bool
    grant_revision: int


class ScenarioPublicationService:
    def __init__(self, readiness: ScenarioReadinessService):
        self.readiness = readiness
        self.integration, self.accounts = readiness.integration, readiness.accounts
        self.scenarios = self.integration.scenarios

    @staticmethod
    def _value(row):
        try:
            value = decoded(ScenarioPublicationManifestV1, row.manifest)
            if (
                value.manifest_digest != row.manifest_digest
                or value.publisher_id != row.publisher_id
                or value.confirmation_id != row.confirmation_id
                or value.published_at.replace(tzinfo=None) != row.published_at
            ):
                raise ValueError("manifest_metadata")
        except INVALID:
            raise ApplicationError(
                "Збережена публікація пошкоджена або не підтримується."
            ) from None
        return Publication(row.id, value)

    def publish(
        self, token, expected: Scenario, *, confirmation_id: str
    ) -> Publication:
        with self.accounts.transaction(write=True) as db:
            current, version = self.integration.emails._current(
                db, token, expected, write=True
            )
            actor = self.accounts.require(
                db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR
            )
            confirmation = db.get(PublicationReview, confirmation_id)
            if (
                confirmation is None
                or confirmation.actor_id != actor.id
                or confirmation.version_id != version.id
            ):
                raise ApplicationError("Підтвердження огляду недійсне або застаріле.")
            try:
                selected = confirmation.payload["selected_group_ids"]
            except (KeyError, TypeError):
                raise ApplicationError("Підтвердження огляду недійсне.") from None
            report, state = self.readiness._evaluate(
                db,
                token,
                current,
                selected_group_ids=selected,
                confirmation_id=confirmation_id,
            )
            if not report.final_ready:
                raise ApplicationError(
                    "Публікацію заблоковано: перевірте джерела, актуальність "
                    "підтвердження та доступ до груп."
                )
            now = datetime.now(UTC)
            content = dict(
                schema_version="scenario-publication-v1",
                snapshot=report.snapshot.model_dump(mode="json"),
                email_schema="email-draft-v2",
                web_schema="web-draft-v3",
                web_renderer="web-renderer-v1",
                link_schema="scenario-link-v1",
                rubric_schema="rubric-definition-v1",
                rubric_semantics="rubric-declarations-v1",
                email_renderer="native-email-v1",
                publisher_id=actor.id,
                published_at=now.isoformat().replace("+00:00", "Z"),
                confirmation_id=confirmation_id,
            )
            manifest = decoded(
                ScenarioPublicationManifestV1,
                content | {"manifest_digest": fingerprint(content)},
            )
            row = ScenarioPublication(
                version_id=state.version_id,
                confirmation_id=confirmation_id,
                publisher_id=actor.id,
                published_at=now.replace(tzinfo=None),
                manifest_digest=manifest.manifest_digest,
                manifest=manifest.model_dump(mode="json"),
            )
            db.add(row)
            db.flush()
            for identifier in report.selected_group_ids:
                db.add(
                    PublicationGroup(
                        publication_id=row.id,
                        group_id=identifier,
                        active=True,
                        revision=1,
                        changed_by=actor.id,
                        changed_at=now.replace(tzinfo=None),
                    )
                )
            # DB triggers append initial audit events in this transaction.
            db.flush()
            version.status = ScenarioStatus.PUBLISHED
            # Status preserves parameter revision/timestamps and source bindings.
            db.flush()
            result = Publication(row.id, manifest)
        return result

    def history(self, token, scenario_id: int) -> tuple[Publication, ...]:
        with self.accounts.transaction() as db:
            actor = self.accounts.require(
                db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR
            )
            self.scenarios._record(db, actor, scenario_id)
            rows = db.scalars(
                select(ScenarioPublication)
                .join(ScenarioVersion)
                .where(ScenarioVersion.scenario_id == scenario_id)
                .order_by(ScenarioVersion.number.desc())
            )
            return tuple(self._value(row) for row in rows)

    def _authorized(self, db, token, publication_id, *, write=False):
        actor = self.accounts.require(db, token, Role.INSTRUCTOR, Role.ADMINISTRATOR)
        row = db.get(ScenarioPublication, publication_id)
        if row is None:
            raise AccessDenied()
        version = db.get(ScenarioVersion, row.version_id)
        self.scenarios._record(db, actor, version.scenario_id, write=write)
        return actor, row

    def grants(self, token, publication_id) -> tuple[GroupGrant, ...]:
        with self.accounts.transaction() as db:
            self._authorized(db, token, publication_id)
            return tuple(
                GroupGrant(g.group_id, g.active, g.revision)
                for g in db.scalars(
                    select(PublicationGroup)
                    .where(PublicationGroup.publication_id == publication_id)
                    .order_by(PublicationGroup.group_id)
                )
            )

    def change_grant(
        self,
        token,
        publication_id: int,
        group_id: int,
        *,
        active: bool,
        expected_revision: int,
    ) -> GroupGrant:
        if type(group_id) is not int or group_id < 1 or type(active) is not bool:
            raise ApplicationError("Некоректна група або операція доступу.")
        with self.accounts.transaction(write=True) as db:
            actor, publication = self._authorized(db, token, publication_id, write=True)
            if active and not authorized_groups(db, actor, (group_id,)):
                raise AccessDenied()
            row = db.get(PublicationGroup, (publication_id, group_id))
            if (row.revision if row else 0) != expected_revision:
                raise ApplicationError("Доступ групи вже змінено. Оновіть список.")
            if row is None and not active or row is not None and row.active == active:
                raise ApplicationError("Доступ уже має цей стан; змін не виконано.")
            now = datetime.now(UTC).replace(tzinfo=None)
            if row is None:
                row = PublicationGroup(publication_id=publication.id, group_id=group_id)
                db.add(row)
            row.active, row.revision = active, expected_revision + 1
            row.changed_by, row.changed_at = actor.id, now
            db.flush()
            result = GroupGrant(group_id, active, row.revision)
        return result

    def audit(self, token, publication_id: int) -> tuple[GrantAuditEvent, ...]:
        with self.accounts.transaction() as db:
            self._authorized(db, token, publication_id)
            return tuple(
                GrantAuditEvent(
                    id=e.id,
                    publication_id=e.publication_id,
                    group_id=e.group_id,
                    actor_id=e.actor_id,
                    operation=e.operation,
                    occurred_at=e.occurred_at.replace(tzinfo=UTC),
                    previous_active=e.previous_active,
                    new_active=e.new_active,
                    grant_revision=e.grant_revision,
                )
                for e in db.scalars(
                    select(PublicationGrantAuditEvent)
                    .where(PublicationGrantAuditEvent.publication_id == publication_id)
                    .order_by(PublicationGrantAuditEvent.id)
                )
            )


class PublicationAccessService:
    """Current effective publication access, shared by discovery and learner writes."""

    def __init__(self, publications: ScenarioPublicationService):
        self.publications = publications
        self.accounts = publications.accounts

    def _eligible(self, db, token):
        actor = self.accounts.require(db, token, Role.LEARNER)
        return tuple(
            db.scalars(
                select(ScenarioPublication)
                .join(ScenarioVersion)
                .join(ScenarioRecord)
                .join(PublicationGroup)
                .join(GroupLearner, GroupLearner.group_id == PublicationGroup.group_id)
                .where(
                    GroupLearner.user_id == actor.id,
                    PublicationGroup.active.is_(True),
                    ScenarioRecord.archived_at.is_(None),
                    ScenarioVersion.status == "published",
                )
                .distinct()
                .order_by(ScenarioVersion.scenario_id, ScenarioVersion.number.desc())
            )
        )

    def catalog(self, token) -> tuple[Publication, ...]:
        with self.accounts.transaction() as db:
            seen, values = set(), []
            for row in self._eligible(db, token):
                value = self.publications._value(row)
                identity = value.manifest.snapshot.scenario_id
                if identity not in seen:
                    seen.add(identity)
                    values.append(value)
            return tuple(values)

    def content(self, token, publication_id: int):
        with self.accounts.transaction() as db:
            return self._content(db, token, publication_id)

    def _content(self, db, token, publication_id: int):
        row = next(
            (r for r in self._eligible(db, token) if r.id == publication_id), None
        )
        if row is None:
            raise AccessDenied()
        value = self.publications._value(row)
        version = db.get(ScenarioVersion, row.version_id)
        record = db.get(ScenarioRecord, version.scenario_id)
        expected = self.publications.scenarios._value(record, version)
        state = self.publications.integration._state(db, expected, version)
        if state.snapshot != value.manifest.snapshot:
            # Archive revision is availability state, not immutable content.
            original = value.manifest.snapshot.model_copy(
                update={"archive_revision": record.archive_revision}
            )
            if state.snapshot != original:
                raise ApplicationError("Джерела публікації не відповідають manifest.")
        return value, state

    def resolve_internal(self, token, publication_id: int) -> InternalNavigationV1:
        value, state = self.content(token, publication_id)
        return InternalNavigationV1(
            publication_id=value.id,
            scenario_id=state.scenario.id,
            scenario_version=state.scenario.version,
            internal_resource_id=state.link.target_resource_id,
            manifest_digest=value.manifest.manifest_digest,
        )
