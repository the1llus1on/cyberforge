"""Application authorization and consistent SQLite snapshots for Analytics."""

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import String, and_, cast, select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import defer

from cyberforge.analytics.aggregation import Learner, aggregate
from cyberforge.analytics.contracts import (
    AnalyticsQueryV1,
    AnalyticsScope,
    GroupOption,
    HistoryQueryV1,
    LearnerAnalyticsHistory,
    PublicationOption,
    ScenarioAnalyticsSnapshotV1,
)
from cyberforge.analytics.recommendations import InstructorRecommendationsService
from cyberforge.application.analytics_history import (
    BATCH_SIZE,
    _HistoricalReader,
    attempt_with_times,
)
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.learning.contracts import utc
from cyberforge.persistence.models import (
    Group,
    GroupInstructor,
    GroupLearner,
    PublicationGroup,
    ScenarioAttemptRecord,
    ScenarioPublication,
    ScenarioRecord,
    ScenarioVersion,
    User,
)


class AnalyticsStorageError(ApplicationError):
    def __init__(self, busy: bool):
        self.code = "STORAGE_BUSY" if busy else "STORAGE_UNAVAILABLE"
        super().__init__(
            "База даних зайнята. Спробуйте ще раз."
            if busy
            else "База даних недоступна. Спробуйте ще раз."
        )


@dataclass(frozen=True)
class AnalyticsAccess:
    """Short-lived local authorization receipt used by presentation and export."""

    actor_id: int
    role: str
    group_ids: tuple[int, ...]
    publication_ids: tuple[int, ...]
    archive_revision: int
    audience: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _Scope:
    record: ScenarioRecord
    groups: dict
    publications: dict
    selected: dict
    access: AnalyticsAccess
    learners: dict
    current: dict


class ScenarioAnalyticsService:
    def __init__(self, evaluations):
        self.evaluations = evaluations
        self.accounts = evaluations.accounts
        self.scenarios = evaluations.publications.scenarios

    @contextmanager
    def _transaction(self, *, publish_file=False):
        try:
            with self.accounts.database.sessions.begin() as db:
                # Reserve the writer slot for the final access check and rename.
                # A concurrent ACL change cannot commit between those operations.
                db.connection().exec_driver_sql(
                    "BEGIN IMMEDIATE" if publish_file else "BEGIN"
                )
                yield db
        except OperationalError as exc:
            message = str(exc.orig).lower()
            raise AnalyticsStorageError(
                "locked" in message or "busy" in message
            ) from None
        except DBAPIError:
            raise AnalyticsStorageError(False) from None

    @staticmethod
    def _query(value):
        # Revalidate model_copy()/model_construct() at the application boundary.
        if isinstance(value, AnalyticsQueryV1):
            value = value.model_dump()
        return AnalyticsQueryV1.model_validate(value)

    @staticmethod
    def _matches(query, user):
        return (
            query.search in user.display_name.casefold()
            or query.search in user.username.casefold()
        )

    def _scope(self, db, token, query):
        actor = self.accounts.require(db, token, Role.ADMINISTRATOR, Role.INSTRUCTOR)
        record = self.scenarios._record(db, actor, query.scenario_id)
        groups = select(Group)
        if actor.role == Role.INSTRUCTOR:
            groups = groups.join(
                GroupInstructor, GroupInstructor.group_id == Group.id
            ).where(GroupInstructor.user_id == actor.id)
        allowed_groups = {g.id: g for g in db.scalars(groups.order_by(Group.id))}
        if query.group_id is not None and query.group_id not in allowed_groups:
            raise AccessDenied()
        publications = {
            pub.id: (pub, version)
            for pub, version in db.execute(
                select(ScenarioPublication, ScenarioVersion)
                .join(
                    ScenarioVersion,
                    ScenarioVersion.id == ScenarioPublication.version_id,
                )
                .where(
                    ScenarioVersion.scenario_id == record.id,
                    ScenarioVersion.status == "published",
                )
                .order_by(ScenarioVersion.number, ScenarioPublication.id)
            )
        }
        if (
            query.publication_id is not None
            and query.publication_id not in publications
        ):
            raise AccessDenied()
        selected = (
            publications
            if query.publication_id is None
            else {query.publication_id: publications[query.publication_id]}
        )
        learners = {}
        current = defaultdict(set)
        if record.archived_at is None and allowed_groups and selected:
            audience = (
                select(User, GroupLearner.group_id)
                .join(GroupLearner, GroupLearner.user_id == User.id)
                .join(
                    PublicationGroup, PublicationGroup.group_id == GroupLearner.group_id
                )
                .join(
                    ScenarioPublication,
                    ScenarioPublication.id == PublicationGroup.publication_id,
                )
                .join(
                    ScenarioVersion,
                    ScenarioVersion.id == ScenarioPublication.version_id,
                )
                .where(
                    ScenarioVersion.scenario_id == record.id,
                    ScenarioVersion.status == "published",
                    User.active.is_(True),
                    User.role == Role.LEARNER,
                    PublicationGroup.active.is_(True),
                )
                .distinct()
            )
            if actor.role == Role.INSTRUCTOR:
                audience = audience.join(
                    GroupInstructor,
                    GroupInstructor.group_id == GroupLearner.group_id,
                ).where(GroupInstructor.user_id == actor.id)
            if query.group_id is not None:
                audience = audience.where(GroupLearner.group_id == query.group_id)
            if query.publication_id is not None:
                audience = audience.where(
                    PublicationGroup.publication_id == query.publication_id
                )
            for user, group_id in db.execute(audience):
                if self._matches(query, user):
                    current[user.id].add(group_id)
                    learners[user.id] = Learner(
                        user.id, user.display_name, user.username
                    )
        access = AnalyticsAccess(
            actor.id,
            actor.role,
            tuple(allowed_groups),
            tuple(selected),
            record.archive_revision,
            tuple(sorted((uid, gid) for uid, gids in current.items() for gid in gids)),
        )
        return _Scope(
            record, allowed_groups, publications, selected, access, learners, current
        )

    def check_access(self, token, value, access):
        query = self._query(value)
        with self._transaction() as db:
            self._recheck(db, token, query, access)

    def _recheck(self, db, token, query, access):
        if self._scope(db, token, query).access != access:
            raise AccessDenied()

    def _attempt_query(self, query, scope):
        attempt = ScenarioAttemptRecord
        condition = [
            attempt.scenario_id == scope.record.id,
            ScenarioVersion.scenario_id == scope.record.id,
            ScenarioVersion.status == "published",
        ]
        if query.publication_id is not None:
            condition.append(attempt.publication_id == query.publication_id)
        if query.group_id is not None:
            condition.append(attempt.authorization_group_id == query.group_id)
        if query.started_from is not None:
            condition.append(
                attempt.started_at >= query.started_from.replace(tzinfo=None)
            )
        if query.started_to is not None:
            condition.append(attempt.started_at < query.started_to.replace(tzinfo=None))
        if query.status is not None:
            condition.append(attempt.status == query.status)
        statement = (
            select(
                attempt,
                User,
                cast(attempt.started_at, String),
                cast(attempt.completed_at, String),
                cast(attempt.abandoned_at, String),
            )
            .options(
                defer(attempt.started_at),
                defer(attempt.completed_at),
                defer(attempt.abandoned_at),
            )
            .join(User, User.id == attempt.learner_id)
            .join(ScenarioPublication, ScenarioPublication.id == attempt.publication_id)
            .join(ScenarioVersion, ScenarioVersion.id == ScenarioPublication.version_id)
            .join(
                PublicationGroup,
                and_(
                    PublicationGroup.publication_id == attempt.publication_id,
                    PublicationGroup.group_id == attempt.authorization_group_id,
                ),
            )
            .where(*condition)
        )
        if scope.access.role == Role.INSTRUCTOR:
            statement = statement.join(
                GroupInstructor,
                GroupInstructor.group_id == attempt.authorization_group_id,
            ).where(GroupInstructor.user_id == scope.access.actor_id)
        return statement

    def _attempts(self, db, query, scope, *, learner_id=None, attempt_id=None):
        if not scope.groups or not scope.selected:
            return
        reader = _HistoricalReader(
            self.evaluations,
            db,
            scope.selected,
            scope.groups,
            include_details=learner_id is not None,
        )
        statement = self._attempt_query(query, scope)
        if learner_id is not None:
            statement = statement.where(ScenarioAttemptRecord.learner_id == learner_id)
        if attempt_id is not None:
            statement = statement.where(ScenarioAttemptRecord.id == str(attempt_id))
        result = db.execute(
            statement.order_by(ScenarioAttemptRecord.id).execution_options(
                yield_per=BATCH_SIZE
            )
        )
        for batch in result.partitions():
            rows = []
            for row, user, started, completed, abandoned in batch:
                if (
                    self._matches(query, user)
                    and row.authorization_group_id in scope.groups
                ):
                    scope.learners[user.id] = Learner(
                        user.id, user.display_name, user.username
                    )
                    rows.append(attempt_with_times(row, started, completed, abandoned))
            if rows:
                yield from reader.read_batch(rows)

    def _metadata(self, db, query, scope):
        # Group options ignore activity filters and include revoked historical grants.
        unfiltered = AnalyticsQueryV1(
            scenario_id=query.scenario_id, publication_id=query.publication_id
        )
        history = (
            self._attempt_query(unfiltered, scope)
            .with_only_columns(ScenarioAttemptRecord.authorization_group_id)
            .distinct()
        )
        group_ids = set(db.scalars(history))
        if scope.record.archived_at is None:
            grants = (
                select(PublicationGroup.group_id)
                .join(
                    ScenarioPublication,
                    ScenarioPublication.id == PublicationGroup.publication_id,
                )
                .join(
                    ScenarioVersion,
                    ScenarioVersion.id == ScenarioPublication.version_id,
                )
                .where(
                    ScenarioVersion.scenario_id == query.scenario_id,
                    ScenarioVersion.status == "published",
                    PublicationGroup.active.is_(True),
                )
                .distinct()
            )
            if query.publication_id is not None:
                grants = grants.where(
                    PublicationGroup.publication_id == query.publication_id
                )
            group_ids.update(db.scalars(grants))
        if query.group_id is not None:
            group_ids.add(query.group_id)
        version = (
            scope.selected[query.publication_id][1]
            if query.publication_id is not None
            else self.scenarios._latest(db, query.scenario_id)
        )
        scenario = self.scenarios._value(scope.record, version)
        return AnalyticsScope(
            name=scenario.name,
            topic=scenario.parameters.topic,
            difficulty=scenario.parameters.difficulty.label,
            audience=scenario.parameters.audience,
            created_at=scenario.created_at,
            status="archived" if scenario.archived else scenario.status.value,
            groups=tuple(
                GroupOption(id=g.id, name=g.name)
                for gid, g in scope.groups.items()
                if gid in group_ids
            ),
            publications=tuple(
                PublicationOption(
                    id=p.id, version=v.number, published_at=utc(p.published_at)
                )
                for p, v in scope.publications.values()
            ),
        )

    def _snapshot(self, db, token, query):
        captured_at = datetime.now(UTC)
        scope = self._scope(db, token, query)
        attempts = tuple(self._attempts(db, query, scope))
        metrics, quality, criteria, rows = aggregate(
            query,
            scope.learners,
            {gid: g.name for gid, g in scope.groups.items()},
            scope.current,
            attempts,
        )
        start = (query.page - 1) * query.page_size
        snapshot = ScenarioAnalyticsSnapshotV1(
            query=query,
            captured_at=captured_at,
            scope=self._metadata(db, query, scope),
            metrics=metrics,
            quality=quality,
            criteria=criteria,
            total_learners=len(rows),
            rows=rows[start : start + query.page_size],
            recommendations=InstructorRecommendationsService.from_aggregates(
                metrics, quality, criteria
            ),
        )
        return snapshot, rows, scope.access

    def load(self, token, value):
        query = self._query(value)
        with self._transaction() as db:
            snapshot, _, access = self._snapshot(db, token, query)
        self.check_access(token, query, access)
        return snapshot, access

    def summary(self, token, value):
        return self.load(token, value)[0]

    def recommendations(self, token, value):
        return self.summary(token, value).recommendations

    def history(self, token, value, details):
        query = self._query(value)
        if isinstance(details, HistoryQueryV1):
            details = details.model_dump()
        details = HistoryQueryV1.model_validate(details)
        with self._transaction() as db:
            captured_at = datetime.now(UTC)
            scope = self._scope(db, token, query)
            attempts = tuple(
                a.detail
                for a in self._attempts(
                    db,
                    query,
                    scope,
                    learner_id=details.learner_id,
                    attempt_id=details.attempt_id,
                )
            )
            if details.result_id is not None:
                attempts = tuple(
                    a for a in attempts if a.result_id == details.result_id
                )
            if not attempts and (
                details.learner_id not in scope.current
                or details.attempt_id is not None
            ):
                raise AccessDenied()
            attempts = sorted(attempts, key=lambda a: a.attempt_id)
            attempts.sort(key=lambda a: a.started_at, reverse=True)
            start = (details.page - 1) * details.page_size
            learner = scope.learners[details.learner_id]
            result = LearnerAnalyticsHistory(
                captured_at=captured_at,
                learner_id=details.learner_id,
                name=learner.name,
                username=learner.username,
                total=len(attempts),
                attempts=tuple(attempts[start : start + details.page_size]),
            )
        self.check_access(token, query, scope.access)
        return result

    def export(self, token, value, path, kind, *, cancelled=lambda: False):
        from cyberforge.analytics.export import write_export

        query = self._query(value)
        if kind not in {"csv", "json"}:
            raise ValueError("unsupported export format")
        with self._transaction() as db:
            snapshot, rows, access = self._snapshot(db, token, query)
        path = Path(path).absolute()
        database_file = Path(self.accounts.database.engine.url.database).resolve()
        protected = {
            database_file,
            *(
                Path(f"{database_file}{suffix}")
                for suffix in ("-wal", "-shm", "-journal")
            ),
        }
        if path.resolve() in protected:
            raise ApplicationError("Виберіть шлях за межами файлів бази даних.")

        @contextmanager
        def authorized():
            with self._transaction(publish_file=True) as db:
                self._recheck(db, token, query, access)
                with self.accounts.sessions.guard(token) as active:
                    if not active or cancelled():
                        raise AccessDenied()
                    yield

        write_export(snapshot, rows, path, kind, authorized)
