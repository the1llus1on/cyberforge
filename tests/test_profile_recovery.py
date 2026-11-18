import hashlib
import json
import os
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest

from cyberforge.application.accounts import AccountService
from cyberforge.application.data_recovery import DataRecoveryService
from cyberforge.domain.accounts import AccessDenied, ApplicationError, Role
from cyberforge.persistence.database import Database
from cyberforge.persistence.profile import DATABASE_NAME, PrivateProfile
from cyberforge.persistence.recovery import ProfileRecovery
from cyberforge.persistence.windows_profile import valid_descriptor

PASSWORD = "synthetic-test-password"


@pytest.fixture
def storage(tmp_path):
    profile = PrivateProfile(tmp_path / "CyberForge")
    with profile.acquire():
        yield ProfileRecovery(profile)


def test_acl_accepts_only_expected_owner_and_inheritance():
    sid = "S-1-5-21-1-2-3-1001"
    entries = "".join(f"(A;OICIID;FA;;;{principal})" for principal in (sid, "SY", "BA"))
    descriptor = f"O:{sid}D:P{entries}"
    assert valid_descriptor(descriptor, sid, directory=True)
    assert not valid_descriptor(descriptor + "(A;;FA;;;WD)", sid, directory=True)
    assert not valid_descriptor(
        descriptor.replace(f"O:{sid}", "O:BA"), sid, directory=True
    )
    assert not valid_descriptor(descriptor.replace("OICIID", "ID"), sid, directory=True)
    assert not valid_descriptor(f"O:{sid}D:NO_ACCESS_CONTROL", sid, directory=True)


def test_profile_refuses_concurrent_lock(storage):
    with pytest.raises(ApplicationError, match="Профіль уже відкрито"):
        with storage.profile.acquire():
            pytest.fail("acquired an already locked profile")


@pytest.mark.skipif(os.name != "nt", reason="uses real Windows ACLs")
def test_windows_profile_rejects_unexpected_sid(tmp_path):
    profile = PrivateProfile(tmp_path / "CyberForge")
    icacls = Path(os.environ["SystemRoot"]) / "System32" / "icacls.exe"
    subprocess.run(
        [icacls, profile.root, "/grant", "*S-1-1-0:(OI)(CI)(RX)"],
        capture_output=True,
        check=True,
        timeout=10,
    )
    with pytest.raises(PermissionError):
        PrivateProfile(profile.root)
    assert not profile.database.exists()


@pytest.mark.skipif(os.name != "posix", reason="uses POSIX permissions and symlinks")
def test_profile_rejects_unsafe_acl_paths_and_database_sidecars(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir(mode=0o755)
    with pytest.raises(PermissionError):
        PrivateProfile(actual)
    actual.chmod(0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(PermissionError):
        PrivateProfile(alias / "nested")
    profile = PrivateProfile(actual)
    (actual / (DATABASE_NAME + "-wal")).symlink_to(tmp_path / "other")
    with pytest.raises(PermissionError):
        with profile.acquire():
            pytest.fail("accepted a redirected sidecar")


def test_online_backup_captures_committed_wal_and_restores(storage):
    database = storage.startup()
    accounts = AccountService(database)
    root = accounts.bootstrap("root", "Адміністратор", PASSWORD)
    token = accounts.login("root", PASSWORD)
    service = DataRecoveryService(accounts, storage)
    try:
        with closing(sqlite3.connect(storage.path)) as writer:
            assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
            writer.execute("UPDATE users SET display_name='Перевірене ім’я'")
            writer.commit()
            assert Path(str(storage.path) + "-wal").stat().st_size > 0
            identifier = service.backup(token)
            writer.execute("UPDATE users SET display_name='Пізніший запис'")
            writer.commit()
        service.plan_restore(token, identifier)
    finally:
        database.close()
    assert service.restore_after_shutdown()
    assert not service.restore_after_shutdown()
    reopened = storage.startup()
    try:
        accounts = AccountService(reopened)
        token = accounts.login("root", PASSWORD)
        assert accounts.current(token).id == root.id
        assert accounts.current(token).display_name == "Перевірене ім’я"
        assert len(storage.available_backups()) == 2
    finally:
        reopened.close()


def test_recovery_service_authorization(storage):
    db = storage.startup()
    try:
        accounts = AccountService(db)
        accounts.bootstrap("root", "Адміністратор", PASSWORD)
        admin = accounts.login("root", PASSWORD)
        accounts.create_user(admin, "learner", "Учень", Role.LEARNER, PASSWORD)
        learner = accounts.login("learner", PASSWORD)
        service = DataRecoveryService(accounts, storage)
        for denied in (None, learner):
            with pytest.raises(AccessDenied):
                service.backup(denied)
            with pytest.raises(AccessDenied):
                service.backups(denied)
            with pytest.raises(AccessDenied):
                service.plan_restore(denied, "a" * 32)
        accounts.logout(admin)
        with pytest.raises(AccessDenied):
            service.backup(admin)
    finally:
        db.close()


def test_concurrent_bootstrap_creates_one_account(storage):
    db = storage.startup()
    accounts = AccountService(db)

    def create(username):
        try:
            return accounts.bootstrap(username, "Адміністратор", PASSWORD)
        except ApplicationError as error:
            assert "вже створено" in str(error)
            return None

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, ("first", "second")))
        (winner,) = tuple(result for result in results if result is not None)
        token = accounts.login(winner.username, PASSWORD)
        assert accounts.list_users(token) == (winner,)
    finally:
        db.close()


def test_old_revision_stages_upgrade_and_retains_accounts(storage):
    database = Database(storage.path)
    try:
        database.upgrade("0001_users_groups")
        AccountService(database).bootstrap("root", "Адміністратор", PASSWORD)
    finally:
        database.close()
    database = storage.startup()
    try:
        accounts = AccountService(database)
        assert (
            accounts.current(accounts.login("root", PASSWORD)).role
            == Role.ADMINISTRATOR
        )
        assert storage._inspect(storage.path) == storage.head
        (identifier,) = storage.available_backups()
        bundle = storage.profile.root / "backups" / identifier
        manifest = json.loads((bundle / "manifest.json").read_text())
        assert manifest["revision"] == "0001_users_groups"
    finally:
        database.close()


@pytest.mark.parametrize("mutation", ["hash", "foreign_schema", "future"])
def test_invalid_backup_preserves_active_database(storage, mutation):
    db = storage.startup()
    db.close()
    identifier = storage.backup()
    bundle = storage.profile.root / "backups" / identifier
    backup = bundle / DATABASE_NAME
    if mutation == "hash":
        with backup.open("ab") as stream:
            stream.write(b"corrupt")
    else:
        with closing(sqlite3.connect(backup)) as connection:
            if mutation == "future":
                connection.execute(
                    "UPDATE alembic_version SET version_num='9000_future'"
                )
            else:
                connection.execute("CREATE TABLE alien (value INTEGER)")
            connection.commit()
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"] = hashlib.sha256(backup.read_bytes()).hexdigest()
        if mutation == "future":
            manifest["revision"] = "9000_future"
        manifest_path.write_text(json.dumps(manifest))
    before = storage.path.read_bytes()
    with pytest.raises(ApplicationError, match="Резервна копія"):
        storage.restore(identifier)
    assert storage.path.read_bytes() == before


def test_future_database_aborts_before_activation(storage):
    storage.startup().close()
    with closing(sqlite3.connect(storage.path)) as connection:
        connection.execute("UPDATE alembic_version SET version_num='9000_future'")
        connection.commit()
    before = storage.path.read_bytes()
    with pytest.raises(ApplicationError, match="несумісна"):
        storage.startup()
    assert storage.path.read_bytes() == before


def test_corrupt_database_emergency_restore_keeps_original(storage):
    storage.startup().close()
    backup = storage.backup()
    corrupt = b"intentionally unreadable test database"
    storage.path.write_bytes(corrupt)
    with pytest.raises(ApplicationError):
        storage.restore(backup)
    assert storage.path.read_bytes() == corrupt
    storage.restore(backup, emergency=True)
    (original,) = (storage.profile.root / "quarantine").glob("*/" + DATABASE_NAME)
    assert original.read_bytes() == corrupt
    storage.startup().close()


def test_failed_activation_leaves_active_and_prior_backup(storage, monkeypatch):
    storage.startup().close()
    identifier = storage.backup()
    before = storage.path.read_bytes()
    backup = storage.profile.root / "backups" / identifier / DATABASE_NAME
    expected_backup = backup.read_bytes()

    def fail_replacement(staged):
        raise OSError("synthetic replacement failure")

    monkeypatch.setattr(storage, "_replace", fail_replacement)
    with pytest.raises(ApplicationError):
        storage.restore(identifier)
    assert storage.path.read_bytes() == before
    assert backup.read_bytes() == expected_backup


def test_busy_backup_preserves_previous_bundle(storage, monkeypatch):
    storage.startup().close()
    identifier = storage.backup()
    ticks = iter((0, 6))
    monkeypatch.setattr(
        "cyberforge.persistence.recovery.monotonic", lambda: next(ticks)
    )
    before = storage.path.read_bytes()
    with closing(sqlite3.connect(storage.path)) as writer:
        writer.execute("BEGIN EXCLUSIVE")
        with pytest.raises(ApplicationError, match="зайнята"):
            storage.backup()
    assert storage.path.read_bytes() == before
    assert storage.available_backups() == (identifier,)
