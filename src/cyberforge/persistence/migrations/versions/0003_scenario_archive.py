"""Add reversible archive metadata without replacing tables or snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0003_scenario_archive"
down_revision = "0002_scenarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenarios", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column(
        "scenarios",
        sa.Column(
            "archive_revision",
            sa.Integer(),
            sa.CheckConstraint(
                "archive_revision >= 0", name="archive_revision_positive"
            ),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(sa.text("DROP TRIGGER scenario_identity_update"))
    op.execute(
        sa.text(
            "CREATE TRIGGER scenario_identity_update BEFORE UPDATE ON scenarios "
            "WHEN NEW.id IS NOT OLD.id OR NEW.owner_id IS NOT OLD.owner_id "
            "OR NEW.created_at IS NOT OLD.created_at "
            "BEGIN SELECT RAISE(ABORT, 'scenario identity is immutable'); END"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER scenario_archive_update BEFORE UPDATE ON scenarios "
            "WHEN (NEW.archived_at IS OLD.archived_at "
            "AND NEW.archive_revision IS NOT OLD.archive_revision) "
            "OR (NEW.archived_at IS NOT OLD.archived_at AND "
            "(NEW.archive_revision != OLD.archive_revision + 1 "
            "OR (NEW.archived_at IS NOT NULL AND OLD.archived_at IS NOT NULL))) "
            "OR (NEW.archived_at IS NOT NULL AND "
            "(typeof(NEW.archived_at) != 'text' "
            "OR julianday(NEW.archived_at) IS NULL)) "
            "BEGIN SELECT RAISE(ABORT, 'invalid archive transition'); END"
        )
    )
    for operation in ("INSERT", "UPDATE", "DELETE"):
        reference = "OLD" if operation == "DELETE" else "NEW"
        # UPDATE must protect both the original and destination parent.
        parent = f"id={reference}.scenario_id"
        if operation == "UPDATE":
            parent = "id IN (OLD.scenario_id, NEW.scenario_id)"
        op.execute(
            sa.text(
                f"CREATE TRIGGER archived_version_{operation.lower()} "
                f"BEFORE {operation} ON scenario_versions "
                f"WHEN EXISTS (SELECT 1 FROM scenarios WHERE {parent} "
                "AND archived_at IS NOT NULL) "
                "BEGIN SELECT RAISE(ABORT, 'archived scenario is read only'); END"
            )
        )


def downgrade() -> None:
    # No table recreation. Downgrade of archived data would silently remove state.
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM scenarios WHERE archive_revision != 0 LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot downgrade scenario archive history")
    op.execute(sa.text("DROP TRIGGER scenario_archive_update"))
    for operation in ("insert", "update", "delete"):
        op.execute(sa.text(f"DROP TRIGGER archived_version_{operation}"))
    op.execute(sa.text("DROP TRIGGER scenario_identity_update"))
    op.drop_column("scenarios", "archive_revision")
    op.drop_column("scenarios", "archived_at")
    op.execute(
        sa.text(
            "CREATE TRIGGER scenario_identity_update BEFORE UPDATE ON scenarios "
            "BEGIN SELECT RAISE(ABORT, 'scenario identity is immutable'); END"
        )
    )
