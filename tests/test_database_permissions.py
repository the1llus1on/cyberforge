"""POSIX confidentiality with a permissive caller umask, isolated in a child."""

import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits only")
@pytest.mark.parametrize("mode", ["DELETE", "WAL"])
def test_private_database_and_sidecars(tmp_path, mode):
    script = """
import os, stat, sys
from pathlib import Path
from cyberforge.persistence.database import Database
root = Path(sys.argv[1])
os.umask(0)
db = Database(root / 'private' / 'nested' / 'data.sqlite3')
assert os.umask(0) == 0
for directory in (root / 'private', root / 'private' / 'nested'):
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
path = root / 'private' / 'nested' / 'data.sqlite3'
assert stat.S_IMODE(path.stat().st_mode) == 0o600
db.upgrade()
with db.engine.connect() as connection:
    connection.exec_driver_sql('PRAGMA journal_mode=' + sys.argv[2])
    connection.commit()
    connection.exec_driver_sql('BEGIN IMMEDIATE')
    connection.exec_driver_sql('CREATE TABLE permissions_probe (id INTEGER)')
    connection.exec_driver_sql('INSERT INTO permissions_probe VALUES (1)')
    suffixes = ('-journal',) if sys.argv[2] == 'DELETE' else ('-wal', '-shm')
    for suffix in suffixes:
        sidecar = Path(str(path) + suffix)
        assert sidecar.exists(), sidecar
        assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600, sidecar
    connection.rollback()
db.close()
existing = root / 'existing'
existing.mkdir(mode=0o755)
file = existing / 'data.sqlite3'
file.write_bytes(b'')
file.chmod(0o640)
db = Database(file)
db.upgrade()
assert stat.S_IMODE(existing.stat().st_mode) == 0o755
assert stat.S_IMODE(file.stat().st_mode) == 0o640
db.close()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(tmp_path), mode],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
