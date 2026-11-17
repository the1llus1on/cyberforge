"""Add durable learner attempts and append-only factual events."""

import sqlalchemy as sa
from alembic import op

revision = "0007_learner_attempts"
down_revision = "0006_scenario_integration_publication"
branch_labels = None
depends_on = None


def execute(sql):
    op.execute(sa.text(sql))


def serialize_ddl():
    connection = op.get_bind()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def upgrade():
    serialize_ddl()
    op.create_table(
        "scenario_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "learner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "publication_id",
            sa.Integer(),
            sa.ForeignKey("scenario_publications.id"),
            nullable=False,
        ),
        sa.Column(
            "scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False
        ),
        sa.Column("scenario_version", sa.Integer(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column(
            "authorization_group_id",
            sa.Integer(),
            sa.ForeignKey("learning_groups.id"),
            nullable=False,
        ),
        sa.Column("scenario_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_stage", sa.String(10), nullable=False),
        sa.Column("email_opened", sa.Boolean(), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("web_visited", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("abandoned_at", sa.DateTime()),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("last_event_sequence", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','COMPLETED','ABANDONED')", name="attempt_status"
        ),
        sa.CheckConstraint("current_stage IN ('EMAIL','WEB')", name="attempt_stage"),
        sa.CheckConstraint(
            "decision IN ('NONE','DECLINED','LEFT')", name="attempt_decision"
        ),
        sa.CheckConstraint(
            "revision > 0 AND last_event_sequence >= 0 AND scenario_version > 0",
            name="attempt_revision",
        ),
        sa.CheckConstraint(
            (
                "(status = 'COMPLETED') = (completed_at IS NOT NULL) AND (status "
                "= 'ABANDONED') = (abandoned_at IS NOT NULL)"
            ),
            name="attempt_terminal_time",
        ),
        sa.CheckConstraint(
            (
                "(completed_at IS NULL OR completed_at >= started_at) AND "
                "(abandoned_at IS NULL OR abandoned_at >= started_at)"
            ),
            name="attempt_time_order",
        ),
        sa.CheckConstraint(
            "current_stage = 'WEB' OR web_visited = 0", name="attempt_visit"
        ),
    )
    op.create_index(
        "uq_active_learner_scenario",
        "scenario_attempts",
        ["learner_id", "scenario_id"],
        unique=True,
        sqlite_where=sa.text("status = 'IN_PROGRESS'"),
    )
    op.create_index(
        "ix_attempt_learner_started", "scenario_attempts", ["learner_id", "started_at"]
    )
    op.create_index("ix_attempt_scenario", "scenario_attempts", ["scenario_id"])
    op.create_index("ix_attempt_publication", "scenario_attempts", ["publication_id"])
    op.create_table(
        "attempt_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.String(36),
            sa.ForeignKey("scenario_attempts.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("surface", sa.String(12), nullable=False),
        sa.Column("action_id", sa.String(32), nullable=False),
        sa.Column("component_id", sa.String(80)),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("operation_digest", sa.String(64), nullable=False),
        sa.Column("operation_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("attempt_id", "sequence", name="attempt_event_sequence"),
        sa.UniqueConstraint(
            "attempt_id", "request_id", "operation_index", name="attempt_event_request"
        ),
        sa.CheckConstraint(
            "sequence > 0 AND operation_index BETWEEN 0 AND 2", name="event_order"
        ),
        sa.CheckConstraint(
            "surface IN ('email','transition','web','system')", name="event_surface"
        ),
    )
    for operation in ("UPDATE", "DELETE"):
        execute(
            f"CREATE TRIGGER event_no_{operation.lower()} BEFORE {operation} "
            "ON attempt_events BEGIN SELECT "
            "RAISE(ABORT, 'immutable attempt event'); END"
        )
    execute(
        "CREATE TRIGGER attempt_no_delete BEFORE DELETE ON "
        "scenario_attempts BEGIN SELECT RAISE(ABORT, 'attempt history "
        "protected'); END"
    )
    identities = (
        "id",
        "learner_id",
        "publication_id",
        "scenario_id",
        "scenario_version",
        "manifest_digest",
        "authorization_group_id",
        "scenario_name",
        "started_at",
    )
    changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in identities)
    execute(
        "CREATE TRIGGER attempt_identity BEFORE UPDATE ON scenario_attempts "
        f"WHEN {changed} OR OLD.status != 'IN_PROGRESS' "
        "OR NEW.revision != OLD.revision+1 "
        "OR NEW.last_event_sequence <= OLD.last_event_sequence "
        "BEGIN SELECT RAISE(ABORT, 'invalid attempt transition'); END"
    )
    execute("""CREATE TRIGGER attempt_event_state BEFORE UPDATE ON scenario_attempts
        WHEN NEW.last_event_sequence != COALESCE(
            (SELECT MAX(sequence) FROM attempt_events WHERE attempt_id=OLD.id),0)
        OR (NEW.status='COMPLETED') != COALESCE((SELECT action_id='completed'
            FROM attempt_events WHERE attempt_id=OLD.id
            ORDER BY sequence DESC LIMIT 1),0)
        OR (NEW.status='ABANDONED') != COALESCE((SELECT action_id='abandoned'
            FROM attempt_events WHERE attempt_id=OLD.id
            ORDER BY sequence DESC LIMIT 1),0)
        OR (NEW.current_stage != OLD.current_stage AND NOT
            (OLD.current_stage='EMAIL' AND NEW.current_stage='WEB' AND
            (SELECT action_id FROM attempt_events WHERE attempt_id=OLD.id
            ORDER BY sequence DESC LIMIT 1)='open_internal'))
        OR NEW.web_visited < OLD.web_visited
        OR (NEW.web_visited > OLD.web_visited AND
            (SELECT action_id FROM attempt_events WHERE attempt_id=OLD.id
            ORDER BY sequence DESC LIMIT 1)!='web_entered')
        BEGIN SELECT RAISE(ABORT, 'attempt event state mismatch'); END""")
    execute("""CREATE TRIGGER attempt_binding BEFORE INSERT ON scenario_attempts
WHEN NOT EXISTS (SELECT 1 FROM scenario_publications p JOIN
        scenario_versions v ON v.id=p.version_id
WHERE p.id=NEW.publication_id AND v.scenario_id=NEW.scenario_id AND
        v.number=NEW.scenario_version AND
        p.manifest_digest=NEW.manifest_digest)
OR NEW.status != 'IN_PROGRESS' OR NEW.current_stage != 'EMAIL' OR
        NEW.last_event_sequence != 0 OR NEW.revision != 1
BEGIN SELECT RAISE(ABORT, 'invalid attempt binding'); END""")
    execute("""CREATE TRIGGER event_append BEFORE INSERT ON attempt_events
WHEN NOT EXISTS (SELECT 1 FROM scenario_attempts a WHERE a.id=NEW.attempt_id
        AND a.status='IN_PROGRESS' AND NEW.timestamp >= a.started_at)
OR NEW.sequence != COALESCE((SELECT MAX(sequence)+1 FROM attempt_events
        WHERE attempt_id=NEW.attempt_id),1)
OR (NEW.surface='web') != (NEW.component_id IS NOT NULL)
OR NOT ((NEW.surface='email' AND NEW.action_id IN
        ('email_opened','inspect_sender','inspect_link','report'))
OR (NEW.surface='transition' AND NEW.action_id IN
        ('decline','open_internal'))
OR (NEW.surface='web' AND NEW.action_id IN
        ('inspect_address','leave','report','confirm','submit_synthetic'))
OR (NEW.surface='system' AND NEW.action_id IN
        ('started','web_entered','completed','abandoned')))
BEGIN SELECT RAISE(ABORT, 'invalid event append'); END""")


def downgrade():
    serialize_ddl()
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM scenario_attempts LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot downgrade learner attempt history")
    op.drop_table("attempt_events")
    op.drop_table("scenario_attempts")
