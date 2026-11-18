"""Validated SQLite snapshots and same-volume activation for private profiles."""

import hashlib
import os
import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from time import monotonic
from uuid import uuid4

from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from cyberforge.domain.accounts import ApplicationError
from cyberforge.persistence.database import Database
from cyberforge.persistence.profile import DATABASE_NAME, PrivateProfile

_INVALID_BACKUP = "Резервна копія пошкоджена або несумісна з цією версією CyberForge."
_INVALID_DATABASE = "База даних пошкоджена або несумісна з цією версією CyberForge."
_BUSY = "База даних зайнята. Закрийте інші екземпляри та повторіть спробу."
_METADATA = "manifest.json"
_SIDECARS = ("-wal", "-shm", "-journal")
_STORAGE_ERRORS = (OSError, ValueError, sqlite3.Error, CommandError, SQLAlchemyError)


class BackupManifest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: str = Field(pattern=r"^cyberforge-backup-v1$")
    revision: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _connect(path: Path, *, readonly: bool) -> sqlite3.Connection:
    mode = "ro" if readonly else "rw"
    return sqlite3.connect(f"{path.as_uri()}?mode={mode}", uri=True, timeout=0.25)


def _checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _schema(db: sqlite3.Connection) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        db.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT GLOB 'sqlite_*' ORDER BY type, name"
        ).fetchall()
    )


def _revision(db: sqlite3.Connection) -> str:
    rows = db.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows) != 1 or not isinstance(rows[0][0], str):
        raise ValueError("invalid_revision")
    return rows[0][0]


class ProfileRecovery:
    """Operations require the caller to hold the profile's process lifetime lock."""

    def __init__(self, profile: PrivateProfile) -> None:
        self.profile = profile
        self.path = profile.database
        config = Database.migration_config()
        script = ScriptDirectory.from_config(config)
        self.head = script.get_current_head()
        self.revisions = frozenset(item.revision for item in script.walk_revisions())
        self._schemas: dict[str, tuple] = {}

    @contextmanager
    def _stage(self) -> Iterator[Path]:
        directory = self.profile.directory("staging/" + uuid4().hex)
        try:
            yield directory
        finally:
            if directory.exists():
                shutil.rmtree(directory, ignore_errors=True)

    def _staging_root(self) -> None:
        self.profile.directory("staging")

    def _upgrade(self, path: Path, revision: str) -> None:
        db = Database(path)
        try:
            db.upgrade(revision)
        finally:
            db.close()

    def _expected_schema(self, revision: str) -> tuple:
        if revision not in self._schemas:
            with self._stage() as staging:
                reference = staging / DATABASE_NAME
                self._upgrade(reference, revision)
                with closing(_connect(reference, readonly=True)) as db:
                    self._schemas[revision] = _schema(db)
        return self._schemas[revision]

    def _inspect(self, path: Path, *, revision: str | None = None) -> str:
        self.profile.validate(path)
        for suffix in _SIDECARS:
            self.profile.validate(path.with_name(path.name + suffix), missing=True)
        with closing(_connect(path, readonly=True)) as db:
            db.execute("BEGIN")
            actual = _revision(db)
            if (
                actual not in self.revisions
                or (revision is not None and actual != revision)
                or _schema(db) != self._expected_schema(actual)
                or db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
                or db.execute("PRAGMA foreign_key_check").fetchone() is not None
            ):
                raise ValueError("invalid_database")
        return actual

    def _snapshot(self, source: Path, destination: Path) -> None:
        self.profile.validate(source)
        self.profile.validate(destination, missing=True)
        if destination.exists():
            raise FileExistsError(destination)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        self.profile.validate(destination)
        deadline = monotonic() + 5

        def bounded(status, remaining, total):
            if monotonic() >= deadline:
                raise ApplicationError(_BUSY)

        with (
            closing(_connect(source, readonly=True)) as live,
            closing(_connect(destination, readonly=False)) as copy,
        ):
            live.backup(copy, pages=128, progress=bounded, sleep=0.025)
            mode = copy.execute("PRAGMA journal_mode=DELETE").fetchone()
            if mode != ("delete",):
                raise ApplicationError(_BUSY)

    def _publish(self, stage: Path, revision: str) -> str:
        copy = stage / DATABASE_NAME
        with copy.open("rb+") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        manifest = BackupManifest(
            schema_version="cyberforge-backup-v1",
            revision=revision,
            sha256=_checksum(copy),
        )
        path = stage / _METADATA
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(manifest.model_dump_json() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.profile.validate(path)
        destination = self.profile.directory("backups") / stage.name
        stage.rename(destination)
        return destination.name

    def backup(self) -> str:
        try:
            self.profile.check_database_paths()
            self._staging_root()
            with self._stage() as stage:
                copy = stage / DATABASE_NAME
                self._snapshot(self.path, copy)
                return self._publish(stage, self._inspect(copy))
        except _STORAGE_ERRORS:
            raise ApplicationError(
                "Не вдалося створити перевірену резервну копію."
            ) from None

    def _check_backup(self, identifier: str, destination: Path) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise ValueError("invalid_backup_identifier")
        bundle = self.profile.root / "backups" / identifier
        self.profile.validate(bundle, directory=True)
        if {path.name for path in bundle.iterdir()} != {_METADATA, DATABASE_NAME}:
            raise ValueError("invalid_backup_contents")
        manifest_path = bundle / _METADATA
        self.profile.validate(manifest_path)
        with manifest_path.open("rb") as stream:
            manifest = BackupManifest.model_validate_json(stream.read(4097))
        source = bundle / DATABASE_NAME
        self.profile.validate(source)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as target, source.open("rb") as live:
            shutil.copyfileobj(live, target)
        if _checksum(destination) != manifest.sha256:
            raise ValueError("backup_hash")
        self._inspect(destination, revision=manifest.revision)

    def _checkpoint(self) -> str:
        with closing(_connect(self.path, readonly=False)) as live:
            if live.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
                raise ApplicationError(_BUSY)
            if live.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                raise ApplicationError(_BUSY)
        self.profile.check_database_paths()
        if any(
            self.path.with_name(self.path.name + suffix).exists()
            for suffix in _SIDECARS
        ):
            raise ApplicationError(_BUSY)
        return _checksum(self.path)

    def _activate(self, staged: Path, original: str | None) -> None:
        self.profile.check_database_paths()
        self.profile.validate(staged)
        with staged.open("rb+") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        if original is None:
            if self.path.exists():
                raise ApplicationError(_BUSY)
            staged.rename(self.path)
            return
        lock = (
            self.profile.windows.lock_for_replacement(self.path)
            if self.profile.windows
            else self.path.open("rb")
        )
        with lock as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != original:
                raise ApplicationError(_BUSY)
            if any(
                self.path.with_name(self.path.name + suffix).exists()
                for suffix in _SIDECARS
            ):
                raise ApplicationError(_BUSY)
            self._replace(staged)

    def _replace(self, stage: Path) -> None:
        if self.profile.windows:
            self.profile.windows.replace(stage, self.path)
        else:
            stage.replace(self.path)

    def startup(self) -> Database:
        try:
            self.profile.check_database_paths()
            self._staging_root()
            if not self.path.exists():
                with self._stage() as stage:
                    target = stage / DATABASE_NAME
                    self._upgrade(target, self.head)
                    self._inspect(target, revision=self.head)
                    self._activate(target, None)
            elif self._inspect(self.path) != self.head:
                original = self._checkpoint()
                self.backup()
                with self._stage() as stage:
                    target = stage / DATABASE_NAME
                    self._snapshot(self.path, target)
                    self._upgrade(target, self.head)
                    self._inspect(target, revision=self.head)
                    self._activate(target, original)
            return Database(self.path)
        except _STORAGE_ERRORS:
            raise ApplicationError(_INVALID_DATABASE) from None

    def restore(self, identifier: str, *, emergency: bool = False) -> None:
        try:
            self.profile.check_database_paths()
            self._staging_root()
            with self._stage() as stage:
                target = stage / DATABASE_NAME
                self._check_backup(identifier, target)
                self._inspect(target, revision=self.head)
                original = None
                if self.path.exists():
                    try:
                        self._inspect(self.path)
                    except (ValueError, sqlite3.DatabaseError):
                        if not emergency or any(
                            self.path.with_name(self.path.name + suffix).exists()
                            for suffix in _SIDECARS
                        ):
                            raise
                        original = _checksum(self.path)
                        self._quarantine(original)
                    else:
                        original = self._checkpoint()
                        self.backup()
                self._activate(target, original)
        except _STORAGE_ERRORS:
            raise ApplicationError(_INVALID_BACKUP) from None

    def _quarantine(self, original: str) -> None:
        """Preserve the exact unreadable file in the same private profile."""
        with self._stage() as stage:
            target = stage / DATABASE_NAME
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as copy, self.path.open("rb") as original_file:
                shutil.copyfileobj(original_file, copy)
                copy.flush()
                os.fsync(copy.fileno())
            if _checksum(target) != original:
                raise ApplicationError(_BUSY)
            stage.rename(self.profile.directory("quarantine") / stage.name)

    def available_backups(self) -> tuple[str, ...]:
        try:
            directory = self.profile.directory("backups")
            return tuple(
                sorted(
                    item.name
                    for item in directory.iterdir()
                    if re.fullmatch(r"[0-9a-f]{32}", item.name)
                )
            )
        except OSError:
            raise ApplicationError("Не вдалося відкрити резервні копії.") from None
