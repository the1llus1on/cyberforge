"""Verify the installed package and its executable entry points."""

import os
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path


def test_installed_package() -> None:
    package = distribution("cyberforge")
    assert package.version == "0.1.0"
    assert any(
        entry.name == "cyberforge" and entry.value == "cyberforge.main:main"
        for entry in package.entry_points
    )


def test_module_runs_outside_repository(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "cyberforge",
            "--smoke-test",
            "--database",
            str(tmp_path / "app.sqlite3"),
        ],
        cwd=tmp_path,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


def test_corrupt_database_startup_is_safe(tmp_path):
    path = tmp_path / "existing.sqlite3"
    original = b"not-a-sqlite-file-preserve-this"
    path.write_bytes(original)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "cyberforge",
            "--database",
            str(path),
            "--smoke-test",
        ],
        capture_output=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 1
    assert "Не вдалося" in result.stderr
    assert "Traceback" not in result.stderr
    assert original.decode() not in result.stderr
    assert path.read_bytes() == original
