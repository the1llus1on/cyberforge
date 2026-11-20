"""Validated SQLite snapshots and same-volume activation for private profiles."""

import hashlib
import os
import re
import shutil
import sqlite3
import stat
from collections.abc import Callable, Iterator
from contextlib import ExitStack, closing, contextmanager
from itertools import zip_longest
from pathlib import Path
from time import monotonic
from uuid import uuid4

from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from cyberforge.domain.accounts import ApplicationError
from cyberforge.persistence.database import Database
from cyberforge.persistence.profile import DATABASE_NAME, PrivateProfile, _file_info

_INVALID_BACKUP = "Резервна копія пошкоджена або несумісна з цією версією CyberForge."
_INVALID_DATABASE = "База даних пошкоджена або несумісна з цією версією CyberForge."
_BUSY = "База даних зайнята. Закрийте інші екземпляри та повторіть спробу."
_METADATA = "manifest.json"
_SIDECARS = ("-wal", "-shm", "-journal")
_STORAGE_ERRORS = (OSError, ValueError, sqlite3.Error, CommandError, SQLAlchemyError)
_LEGACY_PENDING = "legacy-import.pending"
_LEGACY_DONE = "legacy-import.done"
_LEGACY_CONFLICT = (
    "Знайдено стару і приватну бази CyberForge. Жодну не змінено. "
    "Зверніться до відповідального за відновлення даних."
)
_LEGACY_FAILED = (
    "Не вдалося перенести стару базу CyberForge. Стару базу не змінено. "
    "Закрийте старий випуск, перевірте доступ, стан бази та вільне місце."
)


def _import_receipt(path: Path) -> bytes:
    with path.open("rb") as receipt:
        digest = receipt.read(65)
    if not re.fullmatch(rb"[0-9a-f]{64}", digest):
        raise ValueError("invalid_legacy_receipt")
    return digest


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


def _identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _verify_preserved(source: Path, target: Path) -> None:
    """Compare all historical columns, including IDs, hashes and audit rows."""
    with (
        closing(_connect(source, readonly=True)) as before,
        closing(_connect(target, readonly=True)) as after,
    ):
        tables = before.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "name NOT IN ('alembic_version', 'sqlite_stat1', 'sqlite_stat4')"
        )
        for (name,) in tables:
            table = _identifier(name)
            fields = before.execute(f"PRAGMA table_info({table})").fetchall()
            columns = [_identifier(row[1]) for row in fields]
            primary_key = sorted(
                (row[5], _identifier(row[1])) for row in fields if row[5]
            )
            select = f"SELECT {', '.join(columns)} FROM {table}"
            order = ", ".join(column for _, column in primary_key) or "rowid"
            query = f"{select} ORDER BY {order}"
            for old, new in zip_longest(before.execute(query), after.execute(query)):
                if old != new or tuple(map(type, old)) != tuple(map(type, new)):
                    raise ValueError("legacy_data_changed")


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

    def prepare_legacy(
        self, confirm: Callable[[], bool] | None, *, emergency: bool = False
    ) -> bool:
        """Resolve the previous default location before startup or recovery."""
        if self.profile.windows is None:
            raise RuntimeError("legacy import requires Windows file share exclusion")
        source = self.profile.root.parent / DATABASE_NAME
        pending = self.profile.root / _LEGACY_PENDING
        done = self.profile.root / _LEGACY_DONE
        try:
            self.profile.check_database_paths()
            self.profile.validate(pending, missing=True)
            self.profile.validate(done, missing=True)
            if done.exists():
                _import_receipt(done)
                if pending.exists() or (not self.path.exists() and not emergency):
                    raise ApplicationError(_LEGACY_CONFLICT)
                return True
            if pending.exists() and self.path.exists():
                expected = _import_receipt(pending)
                if (
                    any(
                        self.path.with_name(self.path.name + s).exists()
                        for s in _SIDECARS
                    )
                    or _checksum(self.path).encode("ascii") != expected
                ):
                    raise ApplicationError(_LEGACY_CONFLICT)
                self._inspect(self.path, revision=self.head)
                pending.rename(done)
                return True
            found = _file_info(source) is not None
            if not found:
                if pending.exists() or any(
                    _file_info(source.with_name(source.name + s)) is not None
                    for s in _SIDECARS
                ):
                    raise ApplicationError(_LEGACY_CONFLICT)
                return True
            if self.path.exists() or emergency:
                raise ApplicationError(_LEGACY_CONFLICT)
            if any(self.path.with_name(self.path.name + s).exists() for s in _SIDECARS):
                raise ApplicationError(_LEGACY_CONFLICT)
            if confirm is None:
                raise ApplicationError(
                    "Потрібне підтвердження перенесення старої бази."
                )
            if not confirm():
                return False
            self._import_legacy(source, pending, done)
            return True
        except _STORAGE_ERRORS:
            raise ApplicationError(_LEGACY_FAILED) from None

    def _import_legacy(self, source: Path, pending: Path, done: Path) -> None:
        windows = self.profile.windows
        assert windows is not None
        windows.validate_legacy(source.parent, directory=True)
        self._staging_root()
        with ExitStack() as locks:
            files = {}
            # Hold the main file throughout activation. An old instance
            # cannot attach to it while the import is in progress.
            for suffix in ("", *_SIDECARS):
                path = source.with_name(source.name + suffix)
                info = _file_info(path)
                if info is None and suffix:
                    continue
                if info is None or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise PermissionError(path)
                stream = locks.enter_context(windows.lock_legacy_file(path))
                if not os.path.samestat(info, os.fstat(stream.fileno())):
                    raise PermissionError(path)
                windows.validate_legacy(path, directory=False)
                files[suffix] = stream
            if "-journal" in files:
                raise ApplicationError(
                    "Стара база має журнал відновлення. Відкрийте й коректно "
                    "закрийте її старим випуском CyberForge, потім повторіть спробу."
                )
            wal = files.get("-wal")
            if "-shm" in files and wal is None:
                raise ValueError("missing_legacy_wal")
            if wal is not None:
                header = wal.read(32)
                wal.seek(0)
                if header and (
                    len(header) != 32
                    or header[:4] not in (b"\x37\x7f\x06\x82", b"\x37\x7f\x06\x83")
                ):
                    raise ValueError("invalid_legacy_wal")
                files[""].seek(18)
                mode = files[""].read(2)
                files[""].seek(0)
                if header and mode != b"\x02\x02":
                    raise ValueError("unexpected_legacy_wal")
            with (
                self._stage() as raw,
                self._stage() as rollback,
                self._stage() as stage,
            ):
                # Read SQLite only in staging. SHM is a transient WAL index
                # and SQLite reconstructs it from the copied main file and WAL.
                for suffix in ("", "-wal"):
                    if suffix in files:
                        target = raw / (DATABASE_NAME + suffix)
                        fd = os.open(
                            target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                        )
                        with os.fdopen(fd, "wb") as output:
                            shutil.copyfileobj(files[suffix], output)
                raw_db = raw / DATABASE_NAME
                revision = self._inspect(raw_db)
                original = rollback / DATABASE_NAME
                self._snapshot(raw_db, original)
                self._inspect(original, revision=revision)
                candidate = stage / DATABASE_NAME
                self._snapshot(original, candidate)
                self._upgrade(candidate, self.head)
                self._inspect(candidate, revision=self.head)
                _verify_preserved(original, candidate)
                self._publish(rollback, revision)
                receipt = stage / _LEGACY_PENDING
                fd = os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "wb") as output:
                    output.write(_checksum(candidate).encode("ascii"))
                    output.flush()
                    os.fsync(output.fileno())
                receipt.replace(pending)
                self._activate(candidate, None)
                pending.rename(done)

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
