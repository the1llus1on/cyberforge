"""Add saved Email artifacts without altering any existing rows."""

import sqlalchemy as sa
from alembic import op

revision = "0004_email_materials"
down_revision = "0003_scenario_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_materials",
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("scenario_versions.id"),
            primary_key=True,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("scenario_revision", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "revision > 0 AND scenario_revision > 0", name="email_revision"
        ),
        sa.CheckConstraint("schema_version = 'email-draft-v2'", name="email_schema"),
    )
    for operation in ("INSERT", "UPDATE", "DELETE"):
        reference = "OLD" if operation == "DELETE" else "NEW"
        parent = f"v.id={reference}.version_id"
        if operation == "UPDATE":
            parent = "v.id IN (OLD.version_id, NEW.version_id)"
        op.execute(
            sa.text(
                f"CREATE TRIGGER email_protected_{operation.lower()} "
                f"BEFORE {operation} ON email_materials "
                "WHEN EXISTS (SELECT 1 FROM scenario_versions v "
                f"JOIN scenarios s ON s.id=v.scenario_id WHERE {parent} "
                "AND (v.status='published' OR s.archived_at IS NOT NULL)) "
                "BEGIN SELECT RAISE(ABORT, 'email version is read only'); END"
            )
        )
    op.execute(
        sa.text(
            "CREATE TRIGGER email_identity_update BEFORE UPDATE ON email_materials "
            "WHEN NEW.version_id IS NOT OLD.version_id "
            "OR NEW.created_by IS NOT OLD.created_by "
            "OR NEW.created_at IS NOT OLD.created_at "
            "OR NEW.revision != OLD.revision + 1 "
            "BEGIN SELECT RAISE(ABORT, 'invalid email revision'); END"
        )
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM email_materials LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade saved Email material")
    op.drop_table("email_materials")
