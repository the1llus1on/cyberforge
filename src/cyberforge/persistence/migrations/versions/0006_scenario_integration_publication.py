"""Add integration, immutable publication references, grants and append-only audit."""

import sqlalchemy as sa
from alembic import op

revision = "0006_scenario_integration_publication"
down_revision = "0005_web_materials"
branch_labels = None
depends_on = None

TABLES = (
    "scenario_links",
    "rubric_definitions",
    "publication_reviews",
    "scenario_publications",
    "publication_groups",
    "publication_grant_audit",
)


def execute(sql: str) -> None:
    op.execute(sa.text(sql))


def upgrade() -> None:
    for table, constraint in (
        ("scenario_links", "link_revision"),
        ("rubric_definitions", "rubric_revision"),
    ):
        op.create_table(
            table,
            sa.Column(
                "version_id",
                sa.Integer(),
                sa.ForeignKey("scenario_versions.id"),
                primary_key=True,
            ),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.CheckConstraint("revision > 0", name=constraint),
        )
    op.create_table(
        "publication_reviews",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("scenario_versions.id"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "scenario_publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("scenario_versions.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "confirmation_id",
            sa.String(64),
            sa.ForeignKey("publication_reviews.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "publisher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "publication_groups",
        sa.Column(
            "publication_id",
            sa.Integer(),
            sa.ForeignKey("scenario_publications.id"),
            primary_key=True,
        ),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("learning_groups.id"),
            primary_key=True,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("revision > 0", name="grant_revision"),
    )
    op.create_table(
        "publication_grant_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "publication_id",
            sa.Integer(),
            sa.ForeignKey("scenario_publications.id"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("learning_groups.id"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(10), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("previous_active", sa.Boolean(), nullable=False),
        sa.Column("new_active", sa.Boolean(), nullable=False),
        sa.Column("grant_revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "publication_id", "group_id", "grant_revision", name="grant_audit_revision"
        ),
        sa.CheckConstraint("operation IN ('grant','revoke')", name="grant_operation"),
        sa.CheckConstraint(
            "previous_active != new_active AND grant_revision > 0",
            name="grant_transition",
        ),
        sqlite_autoincrement=True,
    )
    for table in (
        "publication_reviews",
        "scenario_publications",
        "publication_grant_audit",
    ):
        for operation in ("UPDATE", "DELETE"):
            execute(
                f"CREATE TRIGGER {table}_{operation.lower()} "
                f"BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'publication history is immutable'); END"
            )
        # REPLACE must also fail when recursive_triggers is off.
        key = "id"
        execute(
            f"CREATE TRIGGER {table}_replace BEFORE INSERT ON {table} "
            f"WHEN EXISTS (SELECT 1 FROM {table} WHERE {key}=NEW.{key}) "
            "BEGIN SELECT RAISE(ABORT, 'history replacement forbidden'); END"
        )
    execute(
        "CREATE TRIGGER publication_audit_replace BEFORE INSERT ON "
        "publication_grant_audit "
        "WHEN EXISTS (SELECT 1 FROM publication_grant_audit WHERE "
        "publication_id=NEW.publication_id "
        "AND group_id=NEW.group_id AND grant_revision=NEW.grant_revision) "
        "BEGIN SELECT RAISE(ABORT, 'audit replacement forbidden'); END"
    )
    execute(
        "CREATE TRIGGER publication_scenario_replace BEFORE INSERT ON scenarios "
        "WHEN EXISTS (SELECT 1 FROM scenarios WHERE id=NEW.id) "
        "BEGIN SELECT RAISE(ABORT, 'scenario identity replacement forbidden'); END"
    )
    for table in ("scenario_links", "rubric_definitions"):
        for operation in ("INSERT", "UPDATE", "DELETE"):
            ref = "OLD" if operation == "DELETE" else "NEW"
            parent = (
                f"v.id={ref}.version_id"
                if operation != "UPDATE"
                else "v.id IN (OLD.version_id,NEW.version_id)"
            )
            execute(
                f"CREATE TRIGGER {table}_{operation.lower()} "
                f"BEFORE {operation} ON {table} "
                "WHEN EXISTS (SELECT 1 FROM scenario_versions v "
                f"JOIN scenarios s ON s.id=v.scenario_id WHERE {parent} "
                "AND (v.status='published' OR s.archived_at IS NOT NULL "
                "OR EXISTS (SELECT 1 FROM scenario_publications p WHERE "
                "p.version_id=v.id))) "
                "BEGIN SELECT RAISE(ABORT, 'integration is read only'); END"
            )
        execute(
            f"CREATE TRIGGER {table}_revision BEFORE UPDATE ON {table} "
            "WHEN NEW.version_id IS NOT OLD.version_id OR NEW.revision != "
            "OLD.revision+1 "
            "BEGIN SELECT RAISE(ABORT, 'invalid integration revision'); END"
        )
    # Existing Phase3/6/7 triggers protect published rows. These additionally
    # protect references between manifest insertion and the final status change.
    for table in (
        "email_materials",
        "web_materials",
        "scenario_links",
        "rubric_definitions",
    ):
        for operation in ("INSERT", "UPDATE", "DELETE"):
            ref = "OLD" if operation == "DELETE" else "NEW"
            condition = (
                f"version_id={ref}.version_id"
                if operation != "UPDATE"
                else "version_id IN (OLD.version_id,NEW.version_id)"
            )
            execute(
                f"CREATE TRIGGER publication_ref_{table}_{operation.lower()} "
                f"BEFORE {operation} ON {table} "
                f"WHEN EXISTS (SELECT 1 FROM scenario_publications WHERE {condition}) "
                "BEGIN SELECT RAISE(ABORT, 'published source is immutable'); END"
            )
    execute(
        "CREATE TRIGGER publication_version_update BEFORE UPDATE ON scenario_versions "
        "WHEN EXISTS (SELECT 1 FROM scenario_publications WHERE "
        "version_id=OLD.id) AND NOT ("
        "OLD.status='draft' AND NEW.status='published' AND NEW.id=OLD.id "
        "AND NEW.scenario_id=OLD.scenario_id AND NEW.number=OLD.number AND "
        "NEW.revision=OLD.revision "
        "AND NEW.parameters=OLD.parameters AND NEW.created_at=OLD.created_at "
        "AND NEW.updated_at=OLD.updated_at) "
        "BEGIN SELECT RAISE(ABORT, 'published source is immutable'); END"
    )
    execute(
        "CREATE TRIGGER publication_version_replace BEFORE INSERT ON scenario_versions "
        "WHEN EXISTS (SELECT 1 FROM scenario_versions WHERE (id=NEW.id OR "
        "(scenario_id=NEW.scenario_id AND number=NEW.number)) AND status='published') "
        "BEGIN SELECT RAISE(ABORT, 'published source replacement forbidden'); END"
    )
    execute(
        "CREATE TRIGGER publication_manifest_replace BEFORE INSERT ON "
        "scenario_publications "
        "WHEN EXISTS (SELECT 1 FROM scenario_publications WHERE "
        "version_id=NEW.version_id OR confirmation_id=NEW.confirmation_id) "
        "BEGIN SELECT RAISE(ABORT, 'publication replacement forbidden'); END"
    )
    execute(
        "CREATE TRIGGER publication_grant_delete BEFORE DELETE ON publication_groups "
        "BEGIN SELECT RAISE(ABORT, 'revoke grants explicitly'); END"
    )
    execute(
        "CREATE TRIGGER publication_grant_insert BEFORE INSERT ON publication_groups "
        "WHEN NEW.revision != 1 OR NEW.active != 1 OR EXISTS (SELECT 1 FROM "
        "publication_groups "
        "WHERE publication_id=NEW.publication_id AND group_id=NEW.group_id) "
        "BEGIN SELECT RAISE(ABORT, 'invalid initial grant'); END"
    )
    execute(
        "CREATE TRIGGER publication_grant_update BEFORE UPDATE ON publication_groups "
        "WHEN NEW.publication_id != OLD.publication_id OR NEW.group_id != OLD.group_id "
        "OR NEW.revision != OLD.revision+1 OR NEW.active=OLD.active "
        "BEGIN SELECT RAISE(ABORT, 'invalid grant transition'); END"
    )
    for operation in ("INSERT", "UPDATE"):
        old = "0" if operation == "INSERT" else "OLD.active"
        execute(
            f"CREATE TRIGGER publication_grant_append_{operation.lower()} "
            f"AFTER {operation} ON publication_groups "
            "BEGIN INSERT INTO publication_grant_audit "
            "(publication_id,group_id,actor_id,operation,occurred_at,previous_a"
            "ctive,new_active,grant_revision) "
            "VALUES (NEW.publication_id,NEW.group_id,NEW.changed_by,"
            "CASE NEW.active WHEN 1 THEN 'grant' ELSE 'revoke' END,"
            f"NEW.changed_at,{old},NEW.active,NEW.revision); END"
        )


def downgrade() -> None:
    for table in TABLES:
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("Cannot downgrade integration/publication/audit data")
    triggers = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name "
                "LIKE 'publication_%'"
            )
        )
        .scalars()
        .all()
    )
    for name in triggers:
        execute(f'DROP TRIGGER "{name}"')
    for table in reversed(TABLES):
        op.drop_table(table)
