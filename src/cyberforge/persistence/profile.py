"""Private application paths and a process-lifetime maintenance lock."""

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cyberforge.domain.accounts import ApplicationError
from cyberforge.persistence.windows_profile import WindowsProfileSecurity

DATABASE_NAME = "cyberforge.sqlite3"
PRIVATE_DIRECTORY = "private"
PROFILE_ERROR = "Приватне сховище недоступне або має небезпечний шлях чи дозволи."


def private_profile_root(app_data_location: Path) -> Path:
    """Return CyberForge's DACL-controlled directory under Qt application data."""
    return app_data_location / PRIVATE_DIRECTORY


def _file_info(path: Path) -> os.stat_result | None:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(status.st_mode) or getattr(status, "st_file_attributes", 0) & 0x400:
        raise PermissionError(PROFILE_ERROR)
    return status


class PrivateProfile:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute() or root == Path(root.anchor) or ".." in root.parts:
            raise PermissionError(PROFILE_ERROR)
        if os.name == "nt" and (
            root.drive.startswith("\\") or any(":" in part for part in root.parts[1:])
        ):
            raise PermissionError(PROFILE_ERROR)
        self.root = root
        self.windows = WindowsProfileSecurity() if os.name == "nt" else None
        self.database = root / DATABASE_NAME
        for parent in reversed(root.parents):
            status = _file_info(parent)
            if status is None:
                parent.mkdir(mode=0o700, exist_ok=True)
                status = _file_info(parent)
            if status is None or not stat.S_ISDIR(status.st_mode):
                raise PermissionError(PROFILE_ERROR)
        if _file_info(root) is None:
            if self.windows:
                self.windows.create_root(root)
            else:
                root.mkdir(mode=0o700, exist_ok=True)
        self.validate(root, directory=True)

    def validate(
        self, path: Path, *, directory: bool = False, missing: bool = False
    ) -> None:
        if not path.is_relative_to(self.root):
            raise PermissionError(PROFILE_ERROR)
        relative = path.relative_to(self.root)
        if ".." in relative.parts or any(":" in part for part in relative.parts):
            raise PermissionError(PROFILE_ERROR)
        if path != self.root:
            self.validate(path.parent, directory=True)
        status = _file_info(path)
        if status is None and missing:
            return
        if status is None:
            raise FileNotFoundError(path)
        right_type = (
            stat.S_ISDIR(status.st_mode)
            if directory
            else stat.S_ISREG(status.st_mode) and status.st_nlink == 1
        )
        if not right_type:
            raise PermissionError(PROFILE_ERROR)
        if self.windows:
            self.windows.validate(path, directory=directory)
        elif status.st_uid != os.getuid() or status.st_mode & 0o077:
            raise PermissionError(PROFILE_ERROR)

    def directory(self, name: str) -> Path:
        path = self.root / name
        self.validate(path, directory=True, missing=True)
        path.mkdir(mode=0o777 if self.windows else 0o700, exist_ok=True)
        self.validate(path, directory=True)
        return path

    def check_database_paths(self) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            self.validate(self.root / (DATABASE_NAME + suffix), missing=True)

    @contextmanager
    def acquire(self) -> Iterator[None]:
        lock = self.root / "profile.lock"
        self.validate(lock, missing=True)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(lock, flags, 0o600)
        try:
            self.validate(lock)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ApplicationError(
                    "Профіль уже відкрито. Закрийте інші екземпляри CyberForge."
                ) from None
            self.check_database_paths()
            yield
        finally:
            os.close(fd)
