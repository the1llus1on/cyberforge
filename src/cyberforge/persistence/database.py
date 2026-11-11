"""SQLite connection policy and packaged Alembic upgrades."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, path: Path) -> None:
        path = path.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
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
