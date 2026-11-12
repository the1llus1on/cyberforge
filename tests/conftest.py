"""Default to headless GUI tests; explicitly select xcb/wayland for WSLg."""

import os
from secrets import token_urlsafe
from types import SimpleNamespace

import pytest

from cyberforge.application.accounts import AccountService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.domain.accounts import Role
from cyberforge.persistence.database import Database

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def scenario_env(tmp_path):
    database = Database(tmp_path / "scenarios.sqlite3")
    database.upgrade()
    accounts = AccountService(database)
    password = token_urlsafe(24)
    accounts.bootstrap("admin", "Адміністратор", password)
    tokens = {"admin": accounts.login("admin", password)}
    for name, role in (
        ("teacher", Role.INSTRUCTOR),
        ("other", Role.INSTRUCTOR),
        ("learner", Role.LEARNER),
    ):
        accounts.create_user(tokens["admin"], name, name, role, password)
        tokens[name] = accounts.login(name, password)
    yield SimpleNamespace(
        database=database,
        accounts=accounts,
        service=ScenarioService(accounts),
        tokens=tokens,
        password=password,
    )
    database.close()
