"""Transactional authentication and user management with service-level RBAC."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256

from sqlalchemy import delete, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from cyberforge.domain.accounts import (
    AccessDenied,
    Account,
    ApplicationError,
    Role,
    Workspace,
)
from cyberforge.identity.passwords import Passwords
from cyberforge.identity.sessions import Sessions
from cyberforge.persistence.database import Database
from cyberforge.persistence.models import GroupInstructor, GroupLearner, User


def account_value(user: User) -> Account:
    return Account(
        user.id, user.username, user.display_name, Role(user.role), user.active
    )


def text_value(value: str, maximum: int, name: str) -> str:
    value = value.strip()
    if not value or len(value) > maximum:
        raise ApplicationError(f"{name}: введіть від 1 до {maximum} символів.")
    return value


def username_value(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
        raise ApplicationError("Логін: 1–80 латинських літер, цифр або символів _ . -")
    return value


class AccountService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.passwords = Passwords()
        self.sessions = Sessions()

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[Session]:
        try:
            with self.database.sessions.begin() as db:
                if write:
                    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
                yield db
        except IntegrityError:
            raise ApplicationError(
                "Запис уже існує або порушує зв’язки даних."
            ) from None
        except DBAPIError:
            raise ApplicationError(
                "База даних недоступна. Спробуйте пізніше."
            ) from None

    def require(self, db: Session, token: str | None, *roles: Role) -> User:
        record = self.sessions.get(token)
        user = db.get(User, record.user_id) if record else None
        if (
            user is None
            or not user.active
            or user.auth_version != record.auth_version
            or sha256(user.password_hash.encode()).hexdigest() != record.credential_tag
        ):
            self.sessions.revoke(token)
            raise AccessDenied()
        if roles and Role(user.role) not in roles:
            raise AccessDenied()
        return user

    def current(self, token: str | None) -> Account:
        with self.transaction() as db:
            return account_value(self.require(db, token))

    def authorize_workspace(self, token: str | None, workspace: Workspace) -> Account:
        roles = {
            Workspace.CONSTRUCTOR: (Role.ADMINISTRATOR, Role.INSTRUCTOR),
            Workspace.ANALYTICS: (Role.ADMINISTRATOR, Role.INSTRUCTOR),
            Workspace.ADMIN: (Role.ADMINISTRATOR,),
            Workspace.MY_SCENARIOS: (Role.LEARNER,),
            Workspace.MY_RESULTS: (Role.LEARNER,),
        }[Workspace(workspace)]
        with self.transaction() as db:
            return account_value(self.require(db, token, *roles))

    def login(
        self, username: str, password: str, *, current_token: str | None = None
    ) -> str:
        if self.sessions.get(current_token):
            raise ApplicationError("Спочатку вийдіть із поточного облікового запису.")
        with self.transaction(write=True) as db:
            user = db.scalar(
                select(User).where(User.username_key == username.strip().casefold())
            )
            valid = self.passwords.verify(
                user.password_hash if user else None, password
            )
            if not valid or user is None or not user.active:
                raise ApplicationError("Невірний логін або пароль.")
            if self.passwords.hasher.check_needs_rehash(user.password_hash):
                user.password_hash = self.passwords.hash(password)
            db.flush()
            user_id, version, encoded = user.id, user.auth_version, user.password_hash
        return self.sessions.issue(user_id, version, encoded)

    def logout(self, token: str | None) -> None:
        self.sessions.revoke(token)

    def list_users(self, token: str | None) -> tuple[Account, ...]:
        with self.transaction() as db:
            self.require(db, token, Role.ADMINISTRATOR)
            return tuple(
                account_value(u) for u in db.scalars(select(User).order_by(User.id))
            )

    def _create(
        self,
        db: Session,
        username: str,
        display_name: str,
        role: Role,
        password: str,
        *,
        active: bool = True,
    ) -> User:
        username = username_value(username)
        user = User(
            username=username,
            username_key=username.casefold(),
            display_name=text_value(display_name, 160, "Ім’я"),
            role=Role(role).value,
            password_hash=self.passwords.hash(password),
            active=active,
            auth_version=1,
        )
        db.add(user)
        db.flush()
        return user

    def create_user(
        self,
        token: str | None,
        username: str,
        display_name: str,
        role: Role,
        password: str,
        *,
        active: bool = True,
    ) -> Account:
        with self.transaction(write=True) as db:
            self.require(db, token, Role.ADMINISTRATOR)
            return account_value(
                self._create(db, username, display_name, role, password, active=active)
            )

    def bootstrap(self, username: str, display_name: str, password: str) -> Account:
        """Explicit local setup only; serialize the empty-database check and insert."""
        with self.transaction(write=True) as db:
            if db.scalar(select(func.count()).select_from(User)):
                raise ApplicationError("Початкового адміністратора вже створено.")
            return account_value(
                self._create(db, username, display_name, Role.ADMINISTRATOR, password)
            )

    def update_user(
        self,
        token: str | None,
        user_id: int,
        display_name: str,
        role: Role,
        active: bool,
        *,
        username: str | None = None,
    ) -> Account:
        with self.transaction(write=True) as db:
            self.require(db, token, Role.ADMINISTRATOR)
            user = db.get(User, user_id)
            if user is None:
                raise ApplicationError("Обліковий запис не знайдено.")
            role = Role(role)
            if (
                user.role == Role.ADMINISTRATOR
                and user.active
                and (role != Role.ADMINISTRATOR or not active)
            ):
                count = db.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.role == Role.ADMINISTRATOR, User.active.is_(True))
                )
                if count == 1:
                    raise ApplicationError(
                        "Не можна вимкнути останнього адміністратора."
                    )
            if role != user.role:
                db.execute(
                    delete(GroupInstructor).where(GroupInstructor.user_id == user_id)
                )
                db.execute(delete(GroupLearner).where(GroupLearner.user_id == user_id))
            if role != user.role or active != user.active:
                user.auth_version += 1
            if username is not None:
                user.username = username_value(username)
                user.username_key = user.username.casefold()
            user.display_name = text_value(display_name, 160, "Ім’я")
            user.role, user.active = role.value, active
            db.flush()
            return account_value(user)

    def change_password(
        self, token: str | None, old_password: str, new_password: str
    ) -> None:
        with self.transaction(write=True) as db:
            user = self.require(db, token)
            if not self.passwords.verify(user.password_hash, old_password):
                raise ApplicationError("Поточний пароль невірний.")
            user.password_hash = self.passwords.hash(new_password)
            user.auth_version += 1
        self.sessions.revoke(token)

    def reset_password(
        self, token: str | None, user_id: int, new_password: str
    ) -> None:
        with self.transaction(write=True) as db:
            self.require(db, token, Role.ADMINISTRATOR)
            user = db.get(User, user_id)
            if user is None:
                raise ApplicationError("Обліковий запис не знайдено.")
            user.password_hash = self.passwords.hash(new_password)
            user.auth_version += 1

    def delete_user(self, token: str | None, user_id: int) -> None:
        from sqlalchemy import inspect, text

        with self.transaction(write=True) as db:
            actor = self.require(db, token, Role.ADMINISTRATOR)
            user = db.get(User, user_id)
            if user is None:
                raise ApplicationError("Обліковий запис не знайдено.")
            if actor.id == user_id:
                raise ApplicationError("Не можна видалити поточного користувача.")
            if user.role == Role.ADMINISTRATOR and user.active:
                count = db.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.role == Role.ADMINISTRATOR, User.active.is_(True))
                )
                if count == 1:
                    raise ApplicationError(
                        "Не можна видалити останнього адміністратора."
                    )
            inspector = inspect(db.connection())
            for table in inspector.get_table_names():
                if table in ("group_instructors", "group_learners"):
                    continue
                for fk in inspector.get_foreign_keys(table):
                    if fk["referred_table"].casefold() == "users":
                        # Never cascade historical data.
                        quote = db.bind.dialect.identifier_preparer.quote
                        predicates = " AND ".join(
                            f"parent.{quote(remote)} = child.{quote(local)}"
                            for local, remote in zip(
                                fk["constrained_columns"],
                                fk["referred_columns"],
                                strict=True,
                            )
                        )
                        query = text(
                            f"SELECT 1 FROM {quote(table)} AS child "
                            "WHERE EXISTS (SELECT 1 FROM users AS parent "
                            f"WHERE parent.id=:id AND {predicates}) LIMIT 1"
                        )
                        if db.execute(query, {"id": user_id}).first():
                            raise ApplicationError(
                                "Є пов’язані дані. Деактивуйте користувача "
                                "замість видалення."
                            )
            db.execute(
                delete(GroupInstructor).where(GroupInstructor.user_id == user_id)
            )
            db.execute(delete(GroupLearner).where(GroupLearner.user_id == user_id))
            db.delete(user)
