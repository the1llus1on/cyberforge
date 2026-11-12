"""SQLite connection policy and packaged Alembic upgrades."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import sessionmaker


def prepare_database_path(path: Path) -> None:
    """Create only missing resources privately; never chmod existing user data.

    SQLite derives journal/WAL/SHM modes from the database file's mode.
    Precreation ensures the first SQLite connection already sees mode 0600.
    """
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return
    else:
        os.close(descriptor)


class Database:
    def __init__(self, path: Path) -> None:
        path = path.expanduser().resolve()
        prepare_database_path(path)
        self.engine = create_engine(
            URL.create("sqlite+pysqlite", database=str(path)), hide_parameters=True
        )

        @event.listens_for(self.engine, "connect")
        def configure(connection, record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def migration_config(self) -> Config:
        config = Config()
        config.set_main_option("script_location", "cyberforge.persistence:migrations")
        return config

    def upgrade(self) -> None:
        config = self.migration_config()
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    def close(self) -> None:
        self.engine.dispose()
