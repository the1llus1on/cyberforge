"""Isolated real migration chain upgrades, rollback, preservation and downgrade."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import event

from cyberforge.persistence.database import Database
from cyberforge.persistence.models import Base
from tests.test_evaluation import frozen  # noqa: F401
from tests.test_evaluation_persistence import runtime  # noqa: F401
from tests.test_scenario_integration import publication_env  # noqa: F401


def migrate(database, direction, target):
    with database.engine.begin() as c:
        cfg = database.migration_config()
        cfg.attributes["connection"] = c
        getattr(command, direction)(cfg, target)


def snapshot(c):
    return {
        t: c.exec_driver_sql("SELECT * FROM " + t).all()
        for t in (
            "users",
            "scenario_versions",
            "scenario_publications",
            "rubric_definitions",
            "scenario_attempts",
            "attempt_events",
        )
    }


def test_upgrade_0007_preserves_data_and_no_backfill(runtime):  # noqa: F811
    e = runtime
    migrate(e.database, "downgrade", "0007_learner_attempts")
    with e.database.engine.connect() as c:
        before = snapshot(c)
    e.database.upgrade()
    with e.database.engine.connect() as c:
        assert before == snapshot(c)
        assert not c.exec_driver_sql("PRAGMA foreign_key_check").all()
        assert not c.exec_driver_sql("SELECT * FROM evaluation_results").all()
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
        assert (
            len(c.exec_driver_sql("PRAGMA foreign_key_list(evaluation_results)").all())
            == 6
        )
        assert c.exec_driver_sql("PRAGMA index_list(evaluation_results)").all()
        assert c.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name IN "
            "('evaluation_results','evaluation_criteria','mentor_feedback')"
        ).all()
    assert e.ev.evaluate(e.learner, e.aid).criteria == e.expected.criteria


def test_multirevision_upgrade_failure_atomic_and_recovery(tmp_path):
    database = Database(tmp_path / "chain.sqlite3")
    try:
        migrate(database, "upgrade", "0005_web_materials")
        with database.engine.connect() as c:
            schema = c.exec_driver_sql(
                "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
            ).all()

        def fail(conn, cursor, sql, params, context, many):
            if sql.lstrip().startswith("CREATE TABLE mentor_feedback"):
                raise RuntimeError("forced migration failure")

        event.listen(database.engine, "before_cursor_execute", fail)
        try:
            with pytest.raises(RuntimeError):
                database.upgrade()
        finally:
            event.remove(database.engine, "before_cursor_execute", fail)
        with database.engine.connect() as c:
            assert (
                MigrationContext.configure(c).get_current_revision()
                == "0005_web_materials"
            )
            assert (
                c.exec_driver_sql(
                    "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
                ).all()
                == schema
            )
        database.upgrade()
        with database.engine.connect() as c:
            assert (
                MigrationContext.configure(c).get_current_revision()
                == "0008_evaluations"
            )
        migrate(database, "downgrade", "0005_web_materials")
        database.upgrade()
    finally:
        database.close()
