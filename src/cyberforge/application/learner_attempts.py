"""Transactional learner execution; all authorization uses current DB state."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from cyberforge.application.scenario_publication import PublicationAccessService
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.learning.contracts import (
    ACTIONS,
    BROWSER_CONTROLS,
    BROWSER_PREFIX,
    AttemptEventV1,
    BrowserControl,
    ScenarioAttemptV1,
    utc,
)
from cyberforge.persistence.models import (
    AttemptEventRecord,
    GroupLearner,
    PublicationGroup,
    ScenarioAttemptRecord,
)
from cyberforge.scenario_integration.contracts import InternalNavigationV1
from cyberforge.web.contracts import fingerprint

RESTRICTED = (
    "Доступ до навчального сценарію обмежено. Спробу збережено; "
    "зверніться до викладача."
)
INVALID = "Дію не виконано. Оновіть проходження та повторіть спробу."


def attempt_value(row):
    fields = {
        key: getattr(row, key)
        for key in ScenarioAttemptV1.model_fields
        if key not in {"schema_version", "attempt_id"}
    }
    for key in ("started_at", "completed_at", "abandoned_at"):
        fields[key] = utc(fields[key])
    return ScenarioAttemptV1(attempt_id=row.id, **fields)


def event_value(row):
    return AttemptEventV1(
        event_id=row.id,
        attempt_id=row.attempt_id,
        sequence=row.sequence,
        surface=row.surface,
        action_id=row.action_id,
        component_id=row.component_id,
        timestamp=utc(row.timestamp),
        request_id=row.request_id,
        operation_digest=row.operation_digest,
        operation_index=row.operation_index,
    )


def identifier(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ApplicationError(INVALID) from None


@dataclass(frozen=True)
class LearnerExercise:
    scenario_id: int
    name: str
    scenario_version: int
    publication_id: int
    attempt: ScenarioAttemptV1 | None
    available: bool


class LearnerAttemptService:
    def __init__(self, access: PublicationAccessService):
        self.access, self.accounts = access, access.accounts

    def _owned(self, db, token, attempt_id):
        actor = self.accounts.require(db, token, Role.LEARNER)
        row = db.get(ScenarioAttemptRecord, identifier(attempt_id))
        if row is None or row.learner_id != actor.id:
            raise AccessDenied()
        return row

    def _bound(self, db, token, row):
        try:
            publication, state = self.access._content(db, token, row.publication_id)
        except AccessDenied:
            raise ApplicationError(RESTRICTED) from None
        if (
            publication.manifest.manifest_digest != row.manifest_digest
            or state.scenario.id != row.scenario_id
            or state.scenario.version != row.scenario_version
        ):
            raise ApplicationError("Публікація не відповідає збереженій спробі.")
        return publication, state

    def history(self, token) -> tuple[ScenarioAttemptV1, ...]:
        with self.accounts.transaction() as db:
            actor = self.accounts.require(db, token, Role.LEARNER)
            return tuple(
                attempt_value(r)
                for r in db.scalars(
                    select(ScenarioAttemptRecord)
                    .where(ScenarioAttemptRecord.learner_id == actor.id)
                    .order_by(
                        ScenarioAttemptRecord.started_at.desc(),
                        ScenarioAttemptRecord.id,
                    )
                )
            )

    def get(self, token, attempt_id):
        with self.accounts.transaction() as db:
            return attempt_value(self._owned(db, token, attempt_id))

    def events(self, token, attempt_id) -> tuple[AttemptEventV1, ...]:
        with self.accounts.transaction() as db:
            row = self._owned(db, token, attempt_id)
            return tuple(
                event_value(e)
                for e in db.scalars(
                    select(AttemptEventRecord)
                    .where(AttemptEventRecord.attempt_id == row.id)
                    .order_by(AttemptEventRecord.sequence)
                )
            )

    def content(self, token, attempt_id):
        with self.accounts.transaction() as db:
            row = self._owned(db, token, attempt_id)
            _, state = self._bound(db, token, row)
            return attempt_value(row), state

    def catalog(self, token) -> tuple[LearnerExercise, ...]:
        with self.accounts.transaction() as db:
            actor = self.accounts.require(db, token, Role.LEARNER)
            eligible = {r.id: r for r in self.access._eligible(db, token)}
            active = {
                r.scenario_id: r
                for r in db.scalars(
                    select(ScenarioAttemptRecord).where(
                        ScenarioAttemptRecord.learner_id == actor.id,
                        ScenarioAttemptRecord.status == "IN_PROGRESS",
                    )
                )
            }
            values = {}
            for pub in eligible.values():
                _, state = self.access._content(db, token, pub.id)
                sid = state.scenario.id
                if sid not in values:
                    values[sid] = LearnerExercise(
                        sid,
                        state.scenario.name,
                        state.scenario.version,
                        pub.id,
                        None,
                        True,
                    )
            for sid, row in active.items():
                values[sid] = LearnerExercise(
                    sid,
                    row.scenario_name,
                    row.scenario_version,
                    row.publication_id,
                    attempt_value(row),
                    row.publication_id in eligible,
                )
            return tuple(values.values())

    def start_or_resume(self, token, scenario_id: int) -> ScenarioAttemptV1:
        if type(scenario_id) is not int or scenario_id < 1:
            raise ApplicationError(INVALID)
        with self.accounts.transaction(write=True) as db:
            actor = self.accounts.require(db, token, Role.LEARNER)
            existing = db.scalar(
                select(ScenarioAttemptRecord).where(
                    ScenarioAttemptRecord.learner_id == actor.id,
                    ScenarioAttemptRecord.scenario_id == scenario_id,
                    ScenarioAttemptRecord.status == "IN_PROGRESS",
                )
            )
            if existing is not None:
                self._bound(db, token, existing)
                return attempt_value(existing)
            selected = next(
                (
                    r
                    for r in self.access._eligible(db, token)
                    if self.access.publications._value(r).manifest.snapshot.scenario_id
                    == scenario_id
                ),
                None,
            )
            if selected is None:
                raise ApplicationError(RESTRICTED)
            publication, state = self.access._content(db, token, selected.id)
            group_id = db.scalar(
                select(PublicationGroup.group_id)
                .join(GroupLearner, GroupLearner.group_id == PublicationGroup.group_id)
                .where(
                    PublicationGroup.publication_id == selected.id,
                    PublicationGroup.active.is_(True),
                    GroupLearner.user_id == actor.id,
                )
                .order_by(PublicationGroup.group_id)
            )
            now = datetime.now(UTC).replace(tzinfo=None)
            row = ScenarioAttemptRecord(
                id=str(uuid4()),
                learner_id=actor.id,
                publication_id=selected.id,
                scenario_id=scenario_id,
                scenario_version=state.scenario.version,
                manifest_digest=publication.manifest.manifest_digest,
                authorization_group_id=group_id,
                scenario_name=state.scenario.name,
                status="IN_PROGRESS",
                current_stage="EMAIL",
                email_opened=False,
                decision="NONE",
                web_visited=False,
                started_at=now,
                completed_at=None,
                abandoned_at=None,
                revision=1,
                last_event_sequence=0,
            )
            db.add(row)
            db.flush()
            AttemptEventService._append(
                db,
                row,
                [("system", "started", None)],
                str(uuid4()),
                fingerprint({"action": "started"}),
                now,
            )
            row.revision += 1
            db.flush()
            return attempt_value(row)


class AttemptEventService:
    """One operation is one IMMEDIATE transaction; request UUID survives retries.

    No text/form/metadata input exists. Web component/action pairs are verified
    against the exact immutable artifact. Replayed requests must match content.
    """

    def __init__(self, attempts: LearnerAttemptService):
        self.attempts, self.accounts = attempts, attempts.accounts

    @staticmethod
    def _append(db, row, actions, request_id, digest, now):
        # Flush events before changing terminal status. Any failure rolls back all.
        sequence = row.last_event_sequence
        for index, (surface, action, component) in enumerate(actions):
            sequence += 1
            value = AttemptEventV1(
                event_id=uuid4(),
                attempt_id=row.id,
                sequence=sequence,
                surface=surface,
                action_id=action,
                component_id=component,
                timestamp=utc(now),
                request_id=request_id,
                operation_digest=digest,
                operation_index=index,
            )
            db.add(
                AttemptEventRecord(
                    id=str(value.event_id),
                    attempt_id=row.id,
                    sequence=sequence,
                    surface=surface,
                    action_id=action,
                    component_id=component,
                    timestamp=now,
                    request_id=request_id,
                    operation_digest=digest,
                    operation_index=index,
                )
            )
        db.flush()
        row.last_event_sequence = sequence

    def record(self, token, attempt_id, **command) -> ScenarioAttemptV1:
        if "_browser" in command or command.get("action_id") == "web_entered":
            raise ApplicationError(INVALID)
        return self._record(token, attempt_id, **command)

    def browser_control(
        self,
        token,
        attempt_id,
        *,
        control: BrowserControl,
        request_id,
        expected_revision: int,
    ) -> ScenarioAttemptV1:
        if not isinstance(control, str) or control not in BROWSER_CONTROLS:
            raise ApplicationError(INVALID)
        return self._record(
            token,
            attempt_id,
            request_id=request_id,
            expected_revision=expected_revision,
            surface="web",
            action_id=control,
            component_id=BROWSER_PREFIX + control,
            _browser=True,
        )

    def _display_acknowledger(self, token, attempt_id):
        """Trusted composition hook; never exposed as a learner command.

        Local Python/DB owners can alter the process. This is API separation,
        not tamper resistance against code execution on the desktop.
        """

        def acknowledge(*, request_id, expected_revision):
            return self._record(
                token,
                attempt_id,
                request_id=request_id,
                expected_revision=expected_revision,
                surface="system",
                action_id="web_entered",
            )

        return acknowledge

    def _record(
        self,
        token,
        attempt_id,
        *,
        request_id,
        expected_revision: int,
        surface: str,
        action_id: str,
        component_id: str | None = None,
        navigation: InternalNavigationV1 | None = None,
        source_message_identifier: str | None = None,
        _browser: bool = False,
    ) -> ScenarioAttemptV1:
        request_id = identifier(request_id)
        if (
            not isinstance(surface, str)
            or not isinstance(action_id, str)
            or (component_id is not None and not isinstance(component_id, str))
            or surface not in ACTIONS
            or action_id not in ACTIONS[surface]
            or action_id == "started"
            or type(expected_revision) is not int
        ):
            raise ApplicationError(INVALID)
        try:
            navigation = (
                InternalNavigationV1.model_validate_json(navigation.model_dump_json())
                if navigation is not None
                else None
            )
            digest = fingerprint(
                dict(
                    surface=surface,
                    action_id=action_id,
                    component_id=component_id,
                    navigation=navigation.model_dump(mode="json")
                    if navigation
                    else None,
                    source_message_identifier=source_message_identifier,
                )
            )
        except (ValueError, TypeError, AttributeError):
            raise ApplicationError(INVALID) from None
        with self.accounts.transaction(write=True) as db:
            row = self.attempts._owned(db, token, attempt_id)
            publication, state = self.attempts._bound(db, token, row)
            previous = db.scalar(
                select(AttemptEventRecord).where(
                    AttemptEventRecord.attempt_id == row.id,
                    AttemptEventRecord.request_id == request_id,
                )
            )
            if previous is not None:
                if previous.operation_digest != digest:
                    raise ApplicationError(
                        "Ідентифікатор дії вже використано для іншої операції."
                    )
                return attempt_value(row)
            if row.status != "IN_PROGRESS" or row.revision != expected_revision:
                raise ApplicationError(INVALID)
            if surface != "web" and component_id is not None:
                raise ApplicationError(INVALID)
            if action_id != "open_internal" and (
                navigation is not None or source_message_identifier is not None
            ):
                raise ApplicationError(INVALID)
            if (
                component_id
                and component_id.startswith(BROWSER_PREFIX)
                and not _browser
            ):
                raise ApplicationError(INVALID)
            actions = [(surface, action_id, component_id)]
            # Compute changes separately; event inserts must precede row updates.
            changes = {}
            if surface == "email":
                if row.current_stage != "EMAIL" or (
                    action_id != "email_opened" and not row.email_opened
                ):
                    raise ApplicationError(INVALID)
                if action_id == "email_opened":
                    changes["email_opened"] = True
            elif surface == "transition":
                if row.current_stage != "EMAIL" or not row.email_opened:
                    raise ApplicationError(INVALID)
                if action_id == "decline":
                    changes["decision"] = "DECLINED"
                else:
                    expected = InternalNavigationV1(
                        publication_id=publication.id,
                        scenario_id=row.scenario_id,
                        scenario_version=row.scenario_version,
                        manifest_digest=row.manifest_digest,
                        internal_resource_id=state.link.target_resource_id,
                    )
                    if (
                        navigation != expected
                        or source_message_identifier
                        != state.link.source_message_identifier
                        or state.link.allowed_action != "open_internal"
                    ):
                        raise ApplicationError("Навчальний перехід недійсний.")
                    changes.update(current_stage="WEB", decision="NONE")
            elif surface == "web":
                pairs = {
                    (c.id, a.id)
                    for c in state.web.page.components
                    for a in getattr(c, "actions", ())
                }
                if (
                    row.current_stage != "WEB"
                    or not row.web_visited
                    or (not _browser and (component_id, action_id) not in pairs)
                ):
                    raise ApplicationError(INVALID)
                if action_id == "leave":
                    changes["decision"] = "LEFT"
            elif action_id == "web_entered":
                if row.current_stage != "WEB":
                    raise ApplicationError(INVALID)
                changes["web_visited"] = True
            elif action_id == "completed":
                if not (
                    (row.current_stage == "EMAIL" and row.decision == "DECLINED")
                    or (row.current_stage == "WEB" and row.web_visited)
                ):
                    raise ApplicationError(INVALID)
                changes["status"] = "COMPLETED"
            elif action_id == "abandoned":
                changes["status"] = "ABANDONED"
            now = datetime.now(UTC).replace(tzinfo=None)
            self._append(db, row, actions, request_id, digest, now)
            if changes.get("status") == "COMPLETED":
                changes["completed_at"] = now
            if changes.get("status") == "ABANDONED":
                changes["abandoned_at"] = now
            for key, value in changes.items():
                setattr(row, key, value)
            row.revision += 1
            db.flush()
            return attempt_value(row)
