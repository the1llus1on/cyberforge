"""Authentication, durable RBAC, and session revocation security tests."""

from pathlib import Path
from secrets import token_urlsafe

import pytest
from sqlalchemy import select

from cyberforge.application.accounts import AccountService
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.groups.service import GroupService
from cyberforge.persistence.database import Database
from cyberforge.persistence.models import User


@pytest.fixture
def accounts(tmp_path: Path):
    database = Database(tmp_path / "accounts.sqlite3")
    database.upgrade()
    service = AccountService(database)
    yield service
    service.sessions.clear()
    database.close()


@pytest.fixture
def password():
    return token_urlsafe(24)


@pytest.fixture
def administrator(accounts, password):
    user = accounts.bootstrap("admin", "Адміністратор", password)
    return user, accounts.login("admin", password)


@pytest.mark.parametrize("role", list(Role))
def test_authentication_roles_and_argon2id(accounts, administrator, password, role):
    _, admin = administrator
    user = accounts.create_user(
        admin, "test_account", "Синтетичне ім’я", role, password
    )
    token = accounts.login(" TEST_ACCOUNT ", password)
    assert accounts.current(token) == user
    with accounts.database.sessions() as db:
        encoded = db.get(User, user.id).password_hash
    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert accounts.passwords.verify(encoded, password)
    assert not accounts.passwords.verify(encoded, token_urlsafe(24))
    assert not accounts.passwords.hasher.check_needs_rehash(encoded)
    assert "password" not in repr(user)
    assert accounts.passwords.hash(password) != encoded


@pytest.mark.parametrize("username", ["admin", "missing", "' OR 1=1 --"])
def test_failed_login_generic(accounts, administrator, username, caplog):
    password = token_urlsafe(24)
    with pytest.raises(ApplicationError, match="Невірний логін або пароль"):
        accounts.login(username, password)
    assert password not in caplog.text


def test_sessions_logout_forgery_and_restart(accounts, administrator, password):
    _, admin = administrator
    second = accounts.login("admin", password)
    assert admin != second
    accounts.logout(admin)
    for token in (admin, None, "forged-token"):
        with pytest.raises(AccessDenied):
            accounts.current(token)
    assert accounts.current(second).role == Role.ADMINISTRATOR
    restarted = AccountService(accounts.database)
    with pytest.raises(AccessDenied):
        restarted.current(second)
    with pytest.raises(ApplicationError, match="Спочатку вийдіть"):
        accounts.login("admin", password, current_token=second)


def test_password_change_revokes_all_sessions(accounts, administrator, password):
    _, token = administrator
    other = accounts.login("admin", password)
    new = token_urlsafe(24)
    with pytest.raises(ApplicationError):
        accounts.change_password(token, "wrong", new)
    with pytest.raises(ApplicationError):
        accounts.change_password(token, password, "short")
    assert accounts.current(token)
    accounts.change_password(token, password, new)
    for session in (token, other):
        with pytest.raises(AccessDenied):
            accounts.current(session)
    with pytest.raises(ApplicationError):
        accounts.login("admin", password)
    assert accounts.current(accounts.login("admin", new))


def test_admin_reset_revokes_across_service_instances(
    accounts, administrator, password
):
    _, admin = administrator
    learner = accounts.create_user(admin, "learner", "Учень", Role.LEARNER, password)
    other = AccountService(accounts.database)
    token = other.login("learner", password)
    replacement = token_urlsafe(24)
    accounts.reset_password(admin, learner.id, replacement)
    with pytest.raises(AccessDenied):
        other.current(token)
    assert other.current(other.login("learner", replacement)) == learner
    assert accounts.current(admin)


def test_disabled_account_and_role_change(accounts, administrator, password):
    _, admin = administrator
    learner = accounts.create_user(admin, "learner", "Учень", Role.LEARNER, password)
    token = accounts.login("learner", password)
    groups = GroupService(accounts)
    group = groups.save_group(admin, "Група")
    groups.set_members(admin, group.id, (), (learner.id,))
    accounts.update_user(admin, learner.id, "Викладач", Role.INSTRUCTOR, True)
    with pytest.raises(AccessDenied):
        accounts.current(token)
    assert not groups.get_group(admin, group.id).learners
    token = accounts.login("learner", password)
    assert accounts.current(token).role == Role.INSTRUCTOR
    accounts.update_user(admin, learner.id, "Викладач", Role.INSTRUCTOR, False)
    with pytest.raises(AccessDenied):
        accounts.current(token)
    with pytest.raises(ApplicationError):
        accounts.login("learner", password)


def test_last_admin_and_bootstrap_protection(accounts, administrator, password):
    user, token = administrator
    for role, active in ((Role.LEARNER, True), (Role.ADMINISTRATOR, False)):
        with pytest.raises(ApplicationError, match="останнього адміністратора"):
            accounts.update_user(token, user.id, user.display_name, role, active)
    with pytest.raises(ApplicationError):
        accounts.bootstrap("intruder", "Інший", password)
    accounts.create_user(token, "second", "Другий", Role.ADMINISTRATOR, password)
    accounts.update_user(token, user.id, "Перший", Role.LEARNER, True)
    with pytest.raises(AccessDenied):
        accounts.current(token)


@pytest.mark.parametrize("role", [None, Role.INSTRUCTOR, Role.LEARNER])
def test_all_administrative_operations_forbidden(
    accounts, administrator, password, role
):
    user, admin = administrator
    token = None
    if role:
        accounts.create_user(admin, "other", "Інший", role, password)
        token = accounts.login("other", password)
    groups = GroupService(accounts)
    group = groups.save_group(admin, "Приватна група")
    operations = (
        lambda: accounts.list_users(token),
        lambda: accounts.create_user(
            token, "intruder", "Інший", Role.ADMINISTRATOR, password
        ),
        lambda: accounts.update_user(token, user.id, "Зміна", Role.LEARNER, False),
        lambda: accounts.reset_password(token, user.id, token_urlsafe(24)),
        lambda: groups.save_group(token, "Заборонена"),
        lambda: groups.save_group(token, "Зміна", group_id=group.id),
        lambda: groups.set_members(token, group.id, (), ()),
        lambda: groups.delete_group(token, group.id),
    )
    for operation in operations:
        with pytest.raises(AccessDenied):
            operation()
    assert groups.get_group(admin, group.id).name == "Приватна група"
    assert len(accounts.list_users(admin)) == (2 if role else 1)


def test_validation_duplicate_and_no_secrets(accounts, administrator, password, caplog):
    _, admin = administrator
    for username, name, candidate in (
        ("bad name", "Ім’я", password),
        ("ok", "", password),
        ("ok", "Ім’я", "short"),
    ):
        with pytest.raises(ApplicationError):
            accounts.create_user(admin, username, name, Role.LEARNER, candidate)
    with pytest.raises(ApplicationError) as error:
        accounts.create_user(admin, "ADMIN", "Дублікат", Role.LEARNER, password)
    assert password not in str(error.value)
    assert password not in caplog.text
    assert "$argon2" not in caplog.text
    with accounts.database.sessions() as db:
        assert len(tuple(db.scalars(select(User)))) == 1


@pytest.mark.parametrize("role", list(Role))
def test_service_workspace_access_matrix(accounts, administrator, password, role):
    from cyberforge.domain.accounts import Workspace

    _, admin = administrator
    accounts.create_user(admin, "workspace_user", "Користувач", role, password)
    token = accounts.login("workspace_user", password)
    allowed = {
        Role.ADMINISTRATOR: {
            Workspace.CONSTRUCTOR,
            Workspace.ANALYTICS,
            Workspace.ADMIN,
        },
        Role.INSTRUCTOR: {Workspace.CONSTRUCTOR, Workspace.ANALYTICS},
        Role.LEARNER: {Workspace.MY_SCENARIOS, Workspace.MY_RESULTS},
    }[role]
    for workspace in Workspace:
        if workspace in allowed:
            assert accounts.authorize_workspace(token, workspace).role == role
        else:
            with pytest.raises(AccessDenied):
                accounts.authorize_workspace(token, workspace)
        with pytest.raises(AccessDenied):
            accounts.authorize_workspace(None, workspace)


def test_rehash_on_login_and_malformed_hash(accounts, administrator, password):
    from argon2 import PasswordHasher, Type

    user, token = administrator
    old = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1, type=Type.ID)
    encoded = old.hash(password)
    with accounts.database.sessions.begin() as db:
        db.get(User, user.id).password_hash = encoded
    assert accounts.passwords.hasher.check_needs_rehash(encoded)
    accounts.login("admin", password)
    with accounts.database.sessions() as db:
        encoded = db.get(User, user.id).password_hash
    assert not accounts.passwords.hasher.check_needs_rehash(encoded)
    assert accounts.current(token)
    assert not accounts.passwords.verify("$argon2id$invalid", password)
    assert not accounts.passwords.verify(None, password)
    assert not accounts.passwords.verify(encoded, "x" * 1025)
