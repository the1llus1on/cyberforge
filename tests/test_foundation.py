"""Verify the installed package and its executable entry points."""

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
        [sys.executable, "-I", "-m", "cyberforge"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CyberForge: базове середовище готове." in result.stdout
    assert result.stderr == ""
