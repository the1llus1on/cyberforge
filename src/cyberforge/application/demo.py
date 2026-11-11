"""Explicit synthetic demo initialization; never runs on normal startup."""

import json
import os
from pathlib import Path
from secrets import token_urlsafe

from sqlalchemy import select

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import ApplicationError, Role
from cyberforge.persistence.models import Group, GroupInstructor, GroupLearner, User

DEMO_USERS = (
    ("Administrator_demo", Role.ADMINISTRATOR),
    ("teacher_demo_1", Role.INSTRUCTOR),
    ("teacher_demo_2", Role.INSTRUCTOR),
    *((f"learner_demo_{i}", Role.LEARNER) for i in range(1, 5)),
)


def initialize_demo(accounts: AccountService, credentials_path: Path) -> bool:
    """Seed once atomically; repeat calls preserve passwords and owner edits."""
    created_file = False
    try:
        with accounts.transaction(write=True) as db:
            existing = set(db.scalars(select(User.username)))
            expected = {name for name, _ in DEMO_USERS}
            if expected <= existing:
                return False
            if existing:
                raise ApplicationError(
                    "Demo потребує порожньої бази. Використайте окремий файл БД."
                )
            credentials = {name: token_urlsafe(24) for name, _ in DEMO_USERS}
            users = {
                name: accounts._create(db, name, name, role, credentials[name])
                for name, role in DEMO_USERS
            }
            for name, teacher, learners in (
                ("Група A", "teacher_demo_1", (1, 2, 3)),
                ("Група B", "teacher_demo_2", (2, 3, 4)),
            ):
                group = Group(name=name, description="Демонстраційна навчальна група")
                db.add(group)
                db.flush()
                db.add(GroupInstructor(group_id=group.id, user_id=users[teacher].id))
                db.add_all(
                    GroupLearner(
                        group_id=group.id, user_id=users[f"learner_demo_{i}"].id
                    )
                    for i in learners
                )
            db.flush()
            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(credentials_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created_file = True
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(credentials, stream, ensure_ascii=False, indent=2)
        return True
    except FileExistsError:
        raise ApplicationError("Файл паролів уже існує. Виберіть новий шлях.") from None
    except BaseException:
        if created_file:
            credentials_path.unlink(missing_ok=True)
        raise
