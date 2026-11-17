"""Persistence, group ownership, constraints, migrations, and demo setup."""

import json
import os
from pathlib import Path
from secrets import token_urlsafe

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from cyberforge.application.accounts import AccountService
from cyberforge.application.demo import DEMO_USERS, initialize_demo
from cyberforge.domain.accounts import AccessDenied, ApplicationError
from cyberforge.groups.service import GroupService
from cyberforge.persistence.database import Database
from cyberforge.persistence.models import Base


@pytest.fixture
def demo(tmp_path):
    path = tmp_path / "demo.sqlite3"
    database = Database(path)
    database.upgrade()
    accounts = AccountService(database)
    credentials = tmp_path / "credentials.json"
    initialize_demo(accounts, credentials)
    passwords = json.loads(credentials.read_text())
    admin = accounts.login("Administrator_demo", passwords["Administrator_demo"])
    yield database, accounts, GroupService(accounts), passwords, admin, credentials
    database.close()


def test_demo_exact_accounts_groups_and_idempotence(demo):
    database, accounts, groups, passwords, admin, credentials = demo
    assert {u.username: u.role for u in accounts.list_users(admin)} == dict(DEMO_USERS)
    assert len(set(passwords.values())) == 7
    a, b = groups.list_groups(admin)
    ids = {u.username: u.id for u in accounts.list_users(admin)}
    assert a.name == "Група A" and b.name == "Група B"
    assert a.instructors == (ids["teacher_demo_1"],)
    assert b.instructors == (ids["teacher_demo_2"],)
    assert a.learners == tuple(ids[f"learner_demo_{i}"] for i in (1, 2, 3))
    assert b.learners == tuple(ids[f"learner_demo_{i}"] for i in (2, 3, 4))
    before = credentials.read_bytes()
    groups.save_group(admin, "Змінена група", group_id=a.id)
    assert not initialize_demo(accounts, credentials)
    assert credentials.read_bytes() == before
    assert groups.get_group(admin, a.id).name == "Змінена група"
    if os.name != "nt":
        assert credentials.stat().st_mode & 0o777 == 0o600


def test_group_scope_and_many_to_many(demo):
    _, accounts, groups, passwords, admin, _ = demo
    a, b = groups.list_groups(admin)
    teacher = accounts.login("teacher_demo_1", passwords["teacher_demo_1"])
    learner = accounts.login("learner_demo_2", passwords["learner_demo_2"])
    assert groups.list_groups(teacher) == (a,)
    assert groups.list_groups(learner) == (a, b)
    with pytest.raises(AccessDenied):
        groups.get_group(teacher, b.id)
    with pytest.raises(AccessDenied):
        groups.get_group(learner, 999)
    groups.set_members(admin, b.id, a.instructors + b.instructors, b.learners)
    assert len(groups.list_groups(teacher)) == 2
    groups.set_members(admin, a.id, (), ())
    assert not groups.get_group(admin, a.id).learners
    groups.delete_group(admin, a.id)
    assert len(groups.list_groups(admin)) == 1


def test_membership_validation_atomicity(demo):
    _, accounts, groups, _, admin, _ = demo
    group = groups.list_groups(admin)[0]
    for instructors, learners in (
        (group.learners, ()),
        ((), group.instructors),
        ((), (999,)),
        ((), group.learners * 2),
    ):
        with pytest.raises(ApplicationError):
            groups.set_members(admin, group.id, instructors, learners)
        assert groups.get_group(admin, group.id) == group
    user = accounts.list_users(admin)[-1]
    accounts.update_user(admin, user.id, user.display_name, user.role, False)
    with pytest.raises(ApplicationError):
        groups.set_members(admin, group.id, (), (user.id,))


def test_restart_persistence_and_revoked_old_token(demo):
    database, accounts, groups, passwords, admin, _ = demo
    group = groups.save_group(admin, "Нова", "Опис")
    ids = groups.list_groups(admin)[0].learners
    groups.set_members(admin, group.id, (), ids)
    path = Path(database.engine.url.database)
    database.close()
    reopened = Database(path)
    reopened.upgrade()
    other = AccountService(reopened)
    with pytest.raises(AccessDenied):
        other.current(admin)
    token = other.login("Administrator_demo", passwords["Administrator_demo"])
    saved = GroupService(other).get_group(token, group.id)
    assert (
        saved.name == "Нова" and saved.description == "Опис" and saved.learners == ids
    )
    reopened.close()


def test_database_constraints_and_migration_consistency(demo):
    database, _, groups, _, admin, _ = demo
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == "0008_evaluations"
        assert compare_metadata(context, Base.metadata) == []
        assert set(inspect(connection).get_table_names()) == set(
            Base.metadata.tables
        ) | {"alembic_version"}
    group = groups.list_groups(admin)[0]
    invalid = (
        ("INSERT INTO group_learners VALUES (:g, 999)", {"g": group.id}),
        (
            "INSERT INTO group_learners VALUES (:g, :u)",
            {"g": group.id, "u": group.learners[0]},
        ),
        (
            "INSERT INTO group_learners VALUES (:g, :u)",
            {"g": group.id, "u": group.instructors[0]},
        ),
        ("UPDATE users SET role='administrator' WHERE id=:u", {"u": group.learners[0]}),
        ("UPDATE users SET role='invalid' WHERE id=:u", {"u": group.instructors[0]}),
    )
    for sql, parameters in invalid:
        with pytest.raises(IntegrityError), database.engine.begin() as connection:
            connection.execute(text(sql), parameters)
    database.upgrade()


def test_migration_downgrade_upgrade(tmp_path):
    database = Database(tmp_path / "migration.sqlite3")
    database.upgrade()
    config = database.migration_config()
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
    database.upgrade()
    assert set(inspect(database.engine).get_table_names()) == set(
        Base.metadata.tables
    ) | {"alembic_version"}
    database.close()


def test_demo_file_collision_rolls_back(tmp_path):
    database = Database(tmp_path / "empty.sqlite3")
    database.upgrade()
    accounts = AccountService(database)
    credentials = tmp_path / "existing.json"
    credentials.write_text("preserve")
    with pytest.raises(ApplicationError):
        initialize_demo(accounts, credentials)
    assert credentials.read_text() == "preserve"
    accounts.bootstrap("normal_admin", "Адміністратор", token_urlsafe(24))
    with pytest.raises(ApplicationError):
        initialize_demo(accounts, tmp_path / "new.json")
    assert not (tmp_path / "new.json").exists()
    database.close()


def test_demo_cli_never_prints_credentials(tmp_path):
    import subprocess
    import sys

    database = tmp_path / "cli.sqlite3"
    credentials = tmp_path / "credentials.json"
    args = [
        sys.executable,
        "-I",
        "-m",
        "cyberforge",
        "--init-demo",
        "--database",
        str(database),
        "--credentials-file",
        str(credentials),
    ]
    result = subprocess.run(
        args, capture_output=True, encoding="utf-8", timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr
    passwords = json.loads(credentials.read_text())
    assert len(passwords) == 7
    for value in passwords.values():
        assert value not in result.stdout + result.stderr
    before = credentials.read_bytes()
    repeated = subprocess.run(
        args, capture_output=True, encoding="utf-8", timeout=30, check=False
    )
    assert repeated.returncode == 0
    assert credentials.read_bytes() == before
    assert "вже існують" in repeated.stdout


def test_atomic_group_save_rollback(demo):
    _, _, groups, _, admin, _ = demo
    group = groups.list_groups(admin)[0]
    with pytest.raises(ApplicationError):
        groups.save_group(
            admin, "Зміна", group_id=group.id, instructors=(), learners=(999,)
        )
    assert groups.get_group(admin, group.id) == group
    with pytest.raises(ApplicationError):
        groups.save_group(admin, "Нова", instructors=(), learners=(999,))
    assert len(groups.list_groups(admin)) == 2
    saved = groups.save_group(
        admin, "Нова", instructors=group.instructors, learners=group.learners
    )
    assert saved.learners == group.learners


@pytest.mark.parametrize("arguments", [{"instructors": ()}, {"learners": ()}])
def test_partial_membership_save_rejected_without_data_loss(demo, arguments):
    _, _, groups, _, token, _ = demo
    group = groups.list_groups(token)[0]
    with pytest.raises(ApplicationError, match="обидва"):
        groups.save_group(token, "Зміна", group_id=group.id, **arguments)
    assert groups.get_group(token, group.id) == group


def test_inactive_members_preserved_but_new_assignment_denied(demo):
    _, accounts, groups, _, token, _ = demo
    a, b = groups.list_groups(token)
    learner_id = a.learners[0]
    user = next(u for u in accounts.list_users(token) if u.id == learner_id)
    accounts.update_user(token, user.id, user.display_name, user.role, False)
    saved = groups.save_group(
        token, a.name, "Опис", a.id, instructors=a.instructors, learners=a.learners
    )
    assert saved.learners == a.learners
    with pytest.raises(ApplicationError):
        groups.set_members(token, b.id, b.instructors, (learner_id,))
    assert groups.get_group(token, b.id) == b
    groups.set_members(token, a.id, a.instructors, ())
    assert not groups.get_group(token, a.id).learners
