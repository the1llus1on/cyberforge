"""Synthetic upgrades from the pre-Phase-12 default SQLite layout."""

import errno
import json
import os
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

import pytest

from cyberforge.analytics.contracts import AnalyticsQueryV1
from cyberforge.application.accounts import AccountService
from cyberforge.application.analytics import ScenarioAnalyticsService
from cyberforge.application.demo import initialize_demo
from cyberforge.application.email_materials import EmailMaterialService
from cyberforge.application.evaluations import EvaluationService
from cyberforge.application.learner_attempts import LearnerAttemptService
from cyberforge.application.learner_demo import prepare_publication
from cyberforge.application.mentor_feedback import MentorFeedbackService
from cyberforge.application.scenario_integration import ScenarioIntegrationService
from cyberforge.application.scenario_publication import (
    PublicationAccessService,
    ScenarioPublicationService,
)
from cyberforge.application.scenario_readiness import ScenarioReadinessService
from cyberforge.application.scenarios import ScenarioService
from cyberforge.application.web_materials import WebMaterialService
from cyberforge.domain.accounts import AccessDenied, ApplicationError
from cyberforge.llm.factory import create_gateway
from cyberforge.persistence.database import Database
from cyberforge.persistence.profile import PrivateProfile, private_profile_root
from cyberforge.persistence.recovery import ProfileRecovery
from cyberforge.persistence.windows_profile import WindowsProfileSecurity
from tests.test_analytics import complete


@pytest.fixture
def profiles(tmp_path):
    # Exercise real Windows sharing and ACLs on Windows. Elsewhere this test
    # double only tests the migration logic with an already quiescent source.
    class ClosedSource:
        def validate(self, path, *, directory):
            pass

        validate_legacy = validate

        def lock_legacy_file(self, path):
            return path.open("rb")

    legacy = PrivateProfile(tmp_path / "Qt data")
    private = PrivateProfile(private_profile_root(legacy.root))
    with private.acquire():
        if os.name != "nt":
            private.windows = ClosedSource()
        yield legacy.database, ProfileRecovery(private)


def seed(path, revision="head"):
    db = Database(path)
    db.upgrade(revision)
    return db


def test_no_legacy_keeps_clean_first_run(profiles):
    legacy, storage = profiles
    assert storage.prepare_legacy(lambda: pytest.fail("unexpected confirmation"))
    with closing(storage.startup()) as db:
        assert AccountService(db).needs_bootstrap()
    assert not legacy.exists()


@pytest.mark.skipif(os.name != "nt", reason="native CPython legacy owner ACL")
def test_migrates_database_with_original_python_created_directory(tmp_path):
    legacy = tmp_path / "old Qt profile" / "cyberforge.sqlite3"
    with closing(seed(legacy, "0008")) as db:
        AccountService(db).bootstrap("root", "Адміністратор", "synthetic-password")
    security = WindowsProfileSecurity()
    icacls = Path(os.environ["SystemRoot"]) / "System32" / "icacls.exe"
    for path in (legacy.parent, legacy):
        # Hosted tests may run elevated. Reproduce ownership of the files
        # created by the old application running under an ordinary token.
        if security._descriptor(path).partition("D:")[0] != f"O:{security.sid}":
            subprocess.run(
                [icacls, path, "/setowner", f"*{security.sid}"],
                check=True,
                capture_output=True,
                timeout=10,
            )
    before = legacy.read_bytes()
    private = PrivateProfile(private_profile_root(legacy.parent))
    with private.acquire():
        storage = ProfileRecovery(private)
        assert storage.prepare_legacy(lambda: True)
        with closing(storage.startup()) as db:
            assert AccountService(db).login("root", "synthetic-password")
    assert legacy.read_bytes() == before


def test_legacy_requires_consent_and_emergency_cannot_bypass_it(profiles):
    legacy, storage = profiles
    seed(legacy).close()
    before = legacy.read_bytes()
    assert not storage.prepare_legacy(lambda: False)
    with pytest.raises(ApplicationError, match="підтвердження"):
        storage.prepare_legacy(None)
    with pytest.raises(ApplicationError):
        storage.prepare_legacy(None, emergency=True)
    assert not storage.path.exists()
    assert legacy.read_bytes() == before


def test_existing_profiles_are_never_overwritten(profiles):
    legacy, storage = profiles
    seed(legacy).close()
    storage.startup().close()
    before = (legacy.read_bytes(), storage.path.read_bytes())
    with pytest.raises(ApplicationError, match="стару і приватну"):
        storage.prepare_legacy(lambda: pytest.fail("ambiguous profiles"))
    assert (legacy.read_bytes(), storage.path.read_bytes()) == before


@pytest.mark.parametrize("failure", ["corrupt", "future", "foreign", "journal", "wal"])
def test_invalid_legacy_leaves_source_unchanged(profiles, failure):
    legacy, storage = profiles
    if failure == "corrupt":
        legacy.write_bytes(b"not a database")
    else:
        seed(legacy).close()
        with closing(sqlite3.connect(legacy)) as connection:
            if failure == "future":
                connection.execute("UPDATE alembic_version SET version_num='9999'")
                connection.commit()
            elif failure == "foreign":
                connection.execute("CREATE TABLE foreign_data (id INTEGER)")
        if failure == "journal":
            legacy.with_name(legacy.name + "-journal").write_bytes(b"journal")
        if failure == "wal":
            legacy.with_name(legacy.name + "-wal").write_bytes(b"corrupt WAL")
    before = legacy.read_bytes()
    with pytest.raises(ApplicationError):
        storage.prepare_legacy(lambda: True)
    assert legacy.read_bytes() == before
    assert not storage.path.exists()


def test_older_schema_disk_full_and_retry(profiles, monkeypatch):
    legacy, storage = profiles
    with closing(seed(legacy, "0007")) as db:
        AccountService(db).bootstrap("root", "Адміністратор", "synthetic-password")
    before = legacy.read_bytes()

    def disk_full(*args):
        raise OSError(errno.ENOSPC, "synthetic disk full")

    with monkeypatch.context() as changes:
        changes.setattr(storage, "_activate", disk_full)
        with pytest.raises(ApplicationError):
            storage.prepare_legacy(lambda: True)
    assert not storage.path.exists()
    assert legacy.read_bytes() == before
    assert storage.available_backups()
    assert storage.prepare_legacy(lambda: True)
    with closing(storage.startup()) as db:
        assert AccountService(db).login("root", "synthetic-password")
    assert legacy.read_bytes() == before


def test_interruption_after_activation_resumes_without_reimport(profiles, monkeypatch):
    legacy, storage = profiles
    seed(legacy).close()
    activate = storage._activate

    def interrupt(*args):
        activate(*args)
        raise KeyboardInterrupt

    with monkeypatch.context() as changes:
        changes.setattr(storage, "_activate", interrupt)
        with pytest.raises(KeyboardInterrupt):
            storage.prepare_legacy(lambda: True)
    for _ in range(2):
        assert storage.prepare_legacy(lambda: pytest.fail("already authorized"))
        storage.startup().close()
    assert len(storage.available_backups()) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing enforcement")
def test_open_legacy_writer_blocks_import(profiles, monkeypatch):
    legacy, storage = profiles
    seed(legacy).close()
    with closing(sqlite3.connect(legacy)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        with pytest.raises(ApplicationError):
            storage.prepare_legacy(lambda: True)
        assert not storage.path.exists()
    activate = storage._activate

    def during_activation(*args):
        with (
            pytest.raises(sqlite3.OperationalError),
            closing(sqlite3.connect(legacy, timeout=0.1)) as old,
        ):
            old.execute("BEGIN IMMEDIATE")
        activate(*args)

    monkeypatch.setattr(storage, "_activate", during_activation)
    assert storage.prepare_legacy(lambda: True)


def test_hardlinked_legacy_is_rejected(profiles):
    legacy, storage = profiles
    seed(legacy).close()
    other = legacy.with_name("same-file.sqlite3")
    other.hardlink_to(legacy)
    with pytest.raises(ApplicationError):
        storage.prepare_legacy(lambda: True)
    assert not storage.path.exists()
    assert other.read_bytes() == legacy.read_bytes()


def test_committed_wal_is_preserved(profiles):
    legacy, storage = profiles
    seed(legacy).close()
    # Freeze the main and committed WAL as they would be after an unclean
    # shutdown, then let the writer close before attempting the import.
    wal = legacy.with_name(legacy.name + "-wal")
    with closing(sqlite3.connect(legacy)) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        main = legacy.read_bytes()
        writer.execute(
            "INSERT INTO learning_groups (name, description) "
            "VALUES ('committed in WAL', '')"
        )
        writer.commit()
        committed = wal.read_bytes()
    legacy.write_bytes(main)
    wal.write_bytes(committed)
    assert storage.prepare_legacy(lambda: True)
    with closing(sqlite3.connect(storage.path)) as db:
        assert db.execute("SELECT name FROM learning_groups").fetchall() == [
            ("committed in WAL",)
        ]
    assert (legacy.read_bytes(), wal.read_bytes()) == (main, committed)


def services(db):
    accounts = AccountService(db)
    gateway = create_gateway()
    emails = EmailMaterialService(ScenarioService(accounts), gateway, demo=True)
    integration = ScenarioIntegrationService(WebMaterialService(emails, demo=True))
    access = PublicationAccessService(
        ScenarioPublicationService(ScenarioReadinessService(integration))
    )
    evaluation = EvaluationService(LearnerAttemptService(access))
    return accounts, evaluation, MentorFeedbackService(evaluation, gateway)


def test_populated_phase11_accounts_scoring_mentor_and_analytics(profiles):
    legacy, storage = profiles
    with closing(seed(legacy, "0008")) as db:
        accounts, evaluation, mentor = services(db)
        credentials_file = legacy.parent / "synthetic-credentials.json"
        initialize_demo(accounts, credentials_file)
        prepare_publication(accounts, credentials_file)
        passwords = json.loads(credentials_file.read_bytes())
        learner = accounts.login("learner_demo_1", passwords["learner_demo_1"])
        (lesson,) = evaluation.attempts.catalog(learner)
        attempt = complete(evaluation, learner, lesson.scenario_id, inspect=True)
        expected = evaluation.evaluate(learner, attempt.attempt_id)
        feedback = mentor.generate(learner, attempt.attempt_id)
        teacher = accounts.login("teacher_demo_1", passwords["teacher_demo_1"])
        query = AnalyticsQueryV1(scenario_id=lesson.scenario_id)
        summary = ScenarioAnalyticsService(evaluation).summary(teacher, query)
    before = legacy.read_bytes()
    assert storage.prepare_legacy(lambda: True)
    with closing(storage.startup()) as db:
        accounts, evaluation, mentor = services(db)
        learner = accounts.login("learner_demo_1", passwords["learner_demo_1"])
        teacher = accounts.login("teacher_demo_1", passwords["teacher_demo_1"])
        outsider = accounts.login("teacher_demo_2", passwords["teacher_demo_2"])
        assert evaluation.evaluate(learner, attempt.attempt_id) == expected
        assert mentor.generate(learner, attempt.attempt_id) == feedback
        analytics = ScenarioAnalyticsService(evaluation)
        assert analytics.summary(teacher, query).model_dump(
            exclude={"captured_at"}
        ) == summary.model_dump(exclude={"captured_at"})
        with pytest.raises(AccessDenied):
            analytics.summary(outsider, query)
    assert legacy.read_bytes() == before
