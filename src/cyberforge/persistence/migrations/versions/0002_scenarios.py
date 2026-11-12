"""Persistent scenario identity and draft/published version boundary."""

import sqlalchemy as sa
from alembic import op

revision = "0002_scenarios"
down_revision = "0001_users_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_scenarios_owner_id", "scenarios", ["owner_id"])
    op.create_table(
        "scenario_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("scenario_id", "number", name="scenario_version_number"),
        sa.CheckConstraint("number > 0 AND revision > 0", name="positive_version"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="scenario_status"),
    )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER published_version_{operation.lower()} "
                f"BEFORE {operation} ON scenario_versions WHEN OLD.status='published' "
                "BEGIN SELECT RAISE(ABORT, 'published version is immutable'); END"
            )
        )
    op.execute(
        sa.text(
            "CREATE TRIGGER scenario_identity_update BEFORE UPDATE ON scenarios "
            "BEGIN SELECT RAISE(ABORT, 'scenario identity is immutable'); END"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER scenario_identity_update"))
    for operation in ("update", "delete"):
        op.execute(sa.text(f"DROP TRIGGER published_version_{operation}"))
    op.drop_table("scenario_versions")
    op.drop_index("ix_scenarios_owner_id", "scenarios")
    op.drop_table("scenarios")
