"""Smoke-test the Windows installer lifecycle in a fresh per-user installation."""

import argparse
import ctypes
import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path

from build_release import PACKAGE_ID, _smoke, digest

_UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall" + (
    "\\{" + PACKAGE_ID + "}_is1"
)
_FLAGS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")


def installed_location():
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _UNINSTALL,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            path, _ = winreg.QueryValueEx(key, "InstallLocation")
            return Path(path)
    except FileNotFoundError:
        return None


def _artifacts(output):
    manifest = json.loads(
        (output / "release-manifest.json").read_text(encoding="utf-8")
    )
    if manifest["application_id"] != PACKAGE_ID:
        raise ValueError("unexpected installer identity")
    (entry,) = [
        value for value in manifest["artifacts"] if value["file"].endswith(".exe")
    ]
    installer = output / entry["file"]
    if installer.name != entry["file"] or digest(installer) != entry["sha256"]:
        raise ValueError("installer manifest digest mismatch")
    return installer, "app-" + manifest["source_sha"][:12]


@contextmanager
def _active_app_mutex():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateMutexW
    create.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    handle = create(None, False, r"Local\CyberForge-Release-v1")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if ctypes.get_last_error() == 183:
            raise RuntimeError("an existing CyberForge instance is running")
        yield
    finally:
        close(handle)


def _test_database():
    from PySide6.QtCore import QCoreApplication, QStandardPaths

    core = QCoreApplication(["CyberForge"])
    core.setApplicationName("CyberForge")
    core.setOrganizationName("CyberForge")
    location = QStandardPaths.StandardLocation.AppLocalDataLocation
    normal = QStandardPaths.writableLocation(location)
    QStandardPaths.setTestModeEnabled(True)
    test_only = QStandardPaths.writableLocation(location)
    if not test_only or test_only == normal:
        raise RuntimeError("Qt test data path is not isolated")
    return Path(test_only) / "cyberforge.sqlite3"


def _install(setup, folder, *, check=True):
    return subprocess.run(
        [str(setup), *_FLAGS, "/SP-", f"/DIR={folder}"],
        check=check,
        timeout=240,
    )


def _uninstall(folder):
    if installed_location() != folder:
        raise RuntimeError("refusing uninstallation outside the test directory")
    (exe,) = folder.glob("unins*.exe")
    subprocess.run([str(exe), *_FLAGS], check=True, timeout=180)
    if installed_location() is not None or list(folder.glob("app-*/CyberForge.exe")):
        raise RuntimeError("per-user uninstallation left managed executables")


def verify(previous, candidate):
    if sys.platform != "win32" or sys.getwindowsversion().build < 22000:
        raise SystemExit("installer lifecycle smoke requires Windows 11 x64")
    if installed_location() is not None:
        raise RuntimeError("an existing user installation must be preserved")
    old_installer, old_dir = _artifacts(previous)
    new_installer, new_dir = _artifacts(candidate)
    if old_dir == new_dir:
        raise ValueError("lifecycle upgrade requires two distinct source commits")
    db = _test_database()
    with tempfile.TemporaryDirectory(prefix="cyberforge-install-smoke-") as temporary:
        folder = Path(temporary) / "Managed CyberForge"
        old_exe = folder / old_dir / "CyberForge.exe"
        new_exe = folder / new_dir / "CyberForge.exe"
        try:
            _install(old_installer, folder)
            if installed_location() != folder:
                raise RuntimeError("missing current-user install registration")
            _smoke(old_exe)
            original = digest(db)
            with _active_app_mutex():
                attempt = _install(new_installer, folder, check=False)
                if attempt.returncode == 0 or new_exe.exists():
                    raise RuntimeError("installer accepted an active application")
            _install(new_installer, folder)
            _smoke(new_exe)
            if digest(db) != original:
                raise RuntimeError("upgrade changed the smoke database")
            _uninstall(folder)
            if digest(db) != original:
                raise RuntimeError("uninstall changed the smoke database")
            _install(new_installer, folder)
            _smoke(new_exe)
            if digest(db) != original:
                raise RuntimeError("reinstall changed the smoke database")
            _uninstall(folder)
        finally:
            if installed_location() == folder:
                _uninstall(folder)
    print("Per-user install, mutex refusal, upgrade, uninstall and reinstall passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    verify(args.previous, args.candidate)


if __name__ == "__main__":
    main()
