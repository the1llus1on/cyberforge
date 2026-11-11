"""Group administration and identity-scoped group reads."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cyberforge.application.accounts import AccountService, text_value
from cyberforge.domain.accounts import (
    AccessDenied,
    ApplicationError,
    LearningGroup,
    Role,
)
from cyberforge.persistence.models import Group, GroupInstructor, GroupLearner, User


class GroupService:
    def __init__(self, accounts: AccountService) -> None:
        self.accounts = accounts

    def _value(self, db: Session, group: Group) -> LearningGroup:
        instructors = tuple(
            db.scalars(
                select(GroupInstructor.user_id)
                .where(GroupInstructor.group_id == group.id)
                .order_by(GroupInstructor.user_id)
            )
        )
        learners = tuple(
            db.scalars(
                select(GroupLearner.user_id)
                .where(GroupLearner.group_id == group.id)
                .order_by(GroupLearner.user_id)
            )
        )
        return LearningGroup(
            group.id, group.name, group.description, instructors, learners
        )

    def list_groups(self, token: str | None) -> tuple[LearningGroup, ...]:
        with self.accounts.transaction() as db:
            user = self.accounts.require(db, token)
            query = select(Group).order_by(Group.id)
            if user.role != Role.ADMINISTRATOR:
                membership = (
                    GroupInstructor if user.role == Role.INSTRUCTOR else GroupLearner
                )
                query = query.join(membership).where(membership.user_id == user.id)
            return tuple(self._value(db, g) for g in db.scalars(query))

    def get_group(self, token: str | None, group_id: int) -> LearningGroup:
        groups = self.list_groups(token)
        group = next((g for g in groups if g.id == group_id), None)
        if group is None:
            raise AccessDenied()
        return group

    def save_group(
        self,
        token: str | None,
        name: str,
        description: str = "",
        group_id: int | None = None,
    ) -> LearningGroup:
        with self.accounts.transaction(write=True) as db:
            self.accounts.require(db, token, Role.ADMINISTRATOR)
            group = db.get(Group, group_id) if group_id is not None else Group()
            if group is None:
                raise ApplicationError("Групу не знайдено.")
            group.name = text_value(name, 120, "Назва групи")
            if len(description) > 1000:
                raise ApplicationError("Опис групи: не більше 1000 символів.")
            group.description = description.strip()
            db.add(group)
            db.flush()
            return self._value(db, group)

    def set_members(
        self,
        token: str | None,
        group_id: int,
        instructors: tuple[int, ...],
        learners: tuple[int, ...],
    ) -> None:
        with self.accounts.transaction(write=True) as db:
            self.accounts.require(db, token, Role.ADMINISTRATOR)
            if db.get(Group, group_id) is None:
                raise ApplicationError("Групу не знайдено.")
            for identifiers, role in (
                (instructors, Role.INSTRUCTOR),
                (learners, Role.LEARNER),
            ):
                if len(set(identifiers)) != len(identifiers):
                    raise ApplicationError("Учасник не може повторюватися у групі.")
                for identifier in identifiers:
                    user = db.get(User, identifier)
                    if user is None or user.role != role or not user.active:
                        raise ApplicationError(
                            "Учасник неактивний або має невідповідну роль."
                        )
            for table, identifiers in (
                (GroupInstructor, instructors),
                (GroupLearner, learners),
            ):
                db.execute(delete(table).where(table.group_id == group_id))
                db.add_all(table(group_id=group_id, user_id=i) for i in identifiers)

    def delete_group(self, token: str | None, group_id: int) -> None:
        with self.accounts.transaction(write=True) as db:
            self.accounts.require(db, token, Role.ADMINISTRATOR)
            group = db.get(Group, group_id)
            if group is None:
                raise ApplicationError("Групу не знайдено.")
            db.delete(group)
