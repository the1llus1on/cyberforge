"""Seal immutable deterministic evaluations and independently committed feedback."""

import sqlalchemy as sa
from alembic import op

revision = "0008_evaluations"
down_revision = "0007_learner_attempts"
branch_labels = None
depends_on = None
TABLES = ("evaluation_results", "evaluation_criteria", "mentor_feedback")


def execute(sql):
    op.execute(sa.text(sql))


def serialize_ddl():
    c = op.get_bind()
    if not c.connection.driver_connection.in_transaction:
        c.exec_driver_sql("BEGIN IMMEDIATE")


def upgrade():
    serialize_ddl()
    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "attempt_id",
            sa.String(36),
            sa.ForeignKey("scenario_attempts.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "learner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False
        ),
        sa.Column(
            "publication_id",
            sa.Integer(),
            sa.ForeignKey("scenario_publications.id"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("scenario_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "rubric_version_id",
            sa.Integer(),
            sa.ForeignKey("rubric_definitions.version_id"),
            nullable=False,
        ),
        sa.Column("scenario_version", sa.Integer(), nullable=False),
        sa.Column("rubric_id", sa.String(80), nullable=False),
        sa.Column("rubric_revision", sa.Integer(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("rubric_digest", sa.String(64), nullable=False),
        sa.Column("scoring_strategy", sa.String(50), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(50)),
        sa.Column("weighted_numerator", sa.Text(), nullable=False),
        sa.Column("weighted_denominator", sa.Text(), nullable=False),
        sa.Column("score_percent", sa.Text()),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("terminal_sequence", sa.Integer(), nullable=False),
        sa.Column("attempt_revision", sa.Integer(), nullable=False),
        sa.Column("events_digest", sa.String(64), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("result_digest", sa.String(64), nullable=False),
        sa.Column("evaluated_at", sa.String(27), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('SCORED','UNSCORABLE')", name="evaluation_status"
        ),
        sa.CheckConstraint(
            (
                "event_count > 0 AND event_count=terminal_sequence AND "
                "attempt_revision=event_count+1"
            ),
            name="evaluation_sequence",
        ),
        sa.CheckConstraint(
            (
                "(status='SCORED' AND reason_code IS NULL AND score_percent "
                "IS NOT NULL AND weighted_denominator!='0') OR "
                "(status='UNSCORABLE' AND "
                "reason_code='NO_APPLICABLE_NUMERICAL_CRITERIA' AND "
                "score_percent IS NULL AND weighted_denominator='0' AND "
                "weighted_numerator='0')"
            ),
            name="evaluation_nulls",
        ),
    )
    op.create_table(
        "evaluation_criteria",
        sa.Column(
            "result_id",
            sa.String(36),
            sa.ForeignKey(
                "evaluation_results.id", deferrable=True, initially="DEFERRED"
            ),
            primary_key=True,
        ),
        sa.Column("criterion_id", sa.String(40), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("applicable", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("weight", sa.Text(), nullable=False),
        sa.Column("weighted_contribution", sa.Text()),
        sa.Column("criterion_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("result_id", "position", name="evaluation_position"),
        sa.CheckConstraint(
            "position BETWEEN 0 AND 7 AND applicable IN (0,1)",
            name="evaluation_detail_position",
        ),
        sa.CheckConstraint(
            (
                "(outcome IN ('MET','NOT_MET') AND applicable=1 AND score IS "
                "NOT NULL AND score IN (0,1) AND score=(outcome='MET') AND "
                "weighted_contribution IS NOT NULL) OR (outcome='DESCRIPTIVE'"
                " AND applicable=1 AND score IS NULL AND "
                "weighted_contribution IS NULL) OR (outcome='NOT_APPLICABLE' "
                "AND applicable=0 AND score IS NULL AND weighted_contribution"
                " IS NULL)"
            ),
            name="evaluation_detail_outcome",
        ),
    )
    op.create_table(
        "mentor_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(36),
            sa.ForeignKey("evaluation_results.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("result_digest", sa.String(64), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("evaluation_status", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("fallback_reason", sa.String(24)),
        sa.Column("provider", sa.String(10)),
        sa.Column("model", sa.String(128)),
        sa.Column("created_at", sa.String(27), nullable=False),
        sa.Column("feedback_digest", sa.String(64), nullable=False),
        sa.Column("feedback_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "mode IN ('DETERMINISTIC','MODEL_SELECTION')", name="feedback_mode"
        ),
    )
    for table in TABLES:
        for operation in ("UPDATE", "DELETE"):
            execute(
                f"CREATE TRIGGER {table}_no_{operation.lower()} "
                f"BEFORE {operation} ON {table} BEGIN SELECT "
                "RAISE(ABORT,'immutable evaluation history'); END"
            )
    execute("""
    CREATE TRIGGER evaluation_detail_insert BEFORE INSERT ON evaluation_criteria
    WHEN EXISTS(SELECT 1 FROM evaluation_results WHERE id=NEW.result_id)
    OR EXISTS(SELECT 1 FROM evaluation_criteria WHERE result_id=NEW.result_id
      AND (criterion_id=NEW.criterion_id OR position=NEW.position))
    OR NOT json_valid(NEW.criterion_json)
    BEGIN SELECT RAISE(ABORT,'sealed or invalid evaluation detail'); END""")
    execute("""
    CREATE TRIGGER evaluation_result_insert BEFORE INSERT ON evaluation_results
    WHEN EXISTS(SELECT 1 FROM evaluation_results WHERE id=NEW.id OR
    attempt_id=NEW.attempt_id)
    OR NOT json_valid(NEW.result_json) OR NOT json_valid(NEW.evidence_json)
    OR NOT EXISTS(SELECT 1 FROM scenario_attempts a JOIN scenario_publications p ON
    p.id=a.publication_id
      JOIN scenario_versions v ON v.id=p.version_id JOIN rubric_definitions r ON
      r.version_id=v.id
      WHERE a.id=NEW.attempt_id AND a.status='COMPLETED' AND a.learner_id=NEW.learner_id
      AND a.scenario_id=NEW.scenario_id AND a.scenario_version=NEW.scenario_version
      AND a.publication_id=NEW.publication_id AND a.manifest_digest=NEW.manifest_digest
      AND v.id=NEW.version_id AND r.version_id=NEW.rubric_version_id
      AND json_extract(r.payload,'$.rubric_id')=NEW.rubric_id AND
      r.revision=NEW.rubric_revision
      AND json_extract(r.payload,'$.content_digest')=NEW.rubric_digest
      AND a.last_event_sequence=NEW.terminal_sequence AND
      a.revision=NEW.attempt_revision)
    OR (SELECT count(*) FROM evaluation_criteria WHERE result_id=NEW.id)
       != (SELECT json_array_length(payload,'$.criteria') FROM rubric_definitions
       WHERE version_id=NEW.rubric_version_id)
    OR json_array_length(NEW.result_json,'$.criteria') != (SELECT count(*) FROM
    evaluation_criteria WHERE result_id=NEW.id)
    OR EXISTS(SELECT 1 FROM rubric_definitions r,json_each(r.payload,'$.criteria')
    expected
      WHERE r.version_id=NEW.rubric_version_id AND NOT EXISTS(SELECT 1 FROM
      evaluation_criteria d
      WHERE d.result_id=NEW.id AND
      d.criterion_id=json_extract(expected.value,'$.criterion_id')))
    OR EXISTS(SELECT 1 FROM evaluation_criteria d WHERE d.result_id=NEW.id AND
      (d.criterion_json IS NOT
      json_extract(NEW.result_json,'$.criteria['||d.position||']')
       OR d.criterion_id IS NOT
       json_extract(d.criterion_json,'$.criterion.criterion_id')
       OR d.position IS NOT json_extract(d.criterion_json,'$.position')
       OR d.applicable IS NOT json_extract(d.criterion_json,'$.applicable')
       OR d.outcome IS NOT json_extract(d.criterion_json,'$.outcome')
       OR d.score IS NOT json_extract(d.criterion_json,'$.score')
       OR d.weight IS NOT json_extract(d.criterion_json,'$.criterion.weight')
       OR d.weighted_contribution IS NOT
       json_extract(d.criterion_json,'$.weighted_contribution')))
    BEGIN SELECT RAISE(ABORT,'incomplete or inconsistent evaluation seal'); END""")
    # Guard every relational projection, including nulls, independently of Python.
    paths = dict(
        id="result_id",
        attempt_id="attempt.attempt_id",
        learner_id="attempt.learner_id",
        scenario_id="attempt.scenario_id",
        publication_id="source.publication_id",
        version_id="source.version_id",
        rubric_version_id="source.version_id",
        scenario_version="attempt.scenario_version",
        rubric_id="source.rubric_id",
        rubric_revision="source.snapshot.rubric_revision",
        rubric_digest="source.snapshot.rubric_digest",
        attempt_revision="attempt.revision",
    )
    for column in ("manifest_digest",):
        paths[column] = "source." + column
    for column in (
        "scoring_strategy",
        "status",
        "reason_code",
        "weighted_numerator",
        "weighted_denominator",
        "score_percent",
        "event_count",
        "terminal_sequence",
        "events_digest",
        "evidence_digest",
        "result_digest",
        "evaluated_at",
    ):
        paths[column] = column
    conditions = " OR ".join(
        f"NEW.{c} IS NOT json_extract(NEW.result_json,'$.{p}')"
        for c, p in paths.items()
    )
    execute(
        "CREATE TRIGGER evaluation_result_projection BEFORE INSERT ON "
        f"evaluation_results WHEN {conditions} BEGIN SELECT "
        "RAISE(ABORT,'evaluation projection mismatch'); END"
    )
    # Canonical order is registry order, never caller selection order.
    ids = (
        "email.sender",
        "email.link",
        "email.report",
        "transition.safe_decline",
        "transition.decision",
        "web.address",
        "web.leave",
        "web.report",
    )
    ordinal = (
        "CASE criterion_id "
        + " ".join(f"WHEN '{i}' THEN {n}" for n, i in enumerate(ids))
        + " ELSE 99 END"
    )
    earlier = ordinal.replace("criterion_id", "earlier.criterion_id")
    current = ordinal.replace("criterion_id", "d.criterion_id")
    execute(f"""
    CREATE TRIGGER evaluation_result_order BEFORE INSERT ON evaluation_results
    WHEN EXISTS(SELECT 1 FROM evaluation_criteria d WHERE d.result_id=NEW.id AND
       d.position != (SELECT count(*) FROM evaluation_criteria earlier
       WHERE earlier.result_id=NEW.id
       AND ({earlier}) < ({current})))
    BEGIN SELECT RAISE(ABORT,'evaluation criterion order'); END""")
    feedback_paths = dict(
        id="feedback_id",
        **{
            k: k
            for k in (
                "result_id",
                "result_digest",
                "evidence_digest",
                "evaluation_status",
                "mode",
                "fallback_reason",
                "provider",
                "model",
                "created_at",
                "feedback_digest",
            )
        },
    )
    conditions = " OR ".join(
        f"NEW.{c} IS NOT json_extract(NEW.feedback_json,'$.{p}')"
        for c, p in feedback_paths.items()
    )
    execute(f"""
    CREATE TRIGGER mentor_feedback_insert BEFORE INSERT ON mentor_feedback
    WHEN EXISTS(SELECT 1 FROM mentor_feedback WHERE id=NEW.id
    OR result_id=NEW.result_id)
    OR NOT json_valid(NEW.feedback_json) OR {conditions}
    OR NOT EXISTS(SELECT 1 FROM evaluation_results r WHERE r.id=NEW.result_id
      AND r.result_digest=NEW.result_digest
      AND r.evidence_digest=NEW.evidence_digest AND r.status=NEW.evaluation_status)
    BEGIN SELECT RAISE(ABORT,'feedback replacement or binding mismatch'); END""")


def downgrade():
    serialize_ddl()
    connection = op.get_bind()
    if any(
        connection.exec_driver_sql(f"SELECT 1 FROM {t} LIMIT 1").first() for t in TABLES
    ):
        raise RuntimeError("Evaluation history exists; unsafe downgrade denied")
    for table in reversed(TABLES):
        op.drop_table(table)
