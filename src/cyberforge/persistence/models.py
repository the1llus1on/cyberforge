"""Identity, groups, and versioned scenario storage."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('administrator', 'instructor', 'learner')", name="user_role"
        ),
        CheckConstraint("length(username) BETWEEN 1 AND 80", name="username_length"),
        CheckConstraint(
            "length(display_name) BETWEEN 1 AND 160", name="display_name_length"
        ),
        CheckConstraint("password_hash LIKE '$argon2id$%'", name="password_argon2id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    username_key: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=1)


class Group(Base):
    __tablename__ = "learning_groups"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 120", name="group_name_length"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(String(1000), default="")


class GroupInstructor(Base):
    __tablename__ = "group_instructors"
    group_id: Mapped[int] = mapped_column(
        ForeignKey("learning_groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class GroupLearner(Base):
    __tablename__ = "group_learners"
    group_id: Mapped[int] = mapped_column(
        ForeignKey("learning_groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class ScenarioRecord(Base):
    __tablename__ = "scenarios"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    archive_revision: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("archive_revision >= 0", name="archive_revision_positive"),
        default=0,
        server_default="0",
    )


class ScenarioVersion(Base):
    __tablename__ = "scenario_versions"
    __table_args__ = (
        UniqueConstraint("scenario_id", "number", name="scenario_version_number"),
        CheckConstraint("number > 0 AND revision > 0", name="positive_version"),
        CheckConstraint("status IN ('draft', 'published')", name="scenario_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"))
    number: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    parameters: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime())
    updated_at: Mapped[datetime] = mapped_column(DateTime())


class EmailMaterial(Base):
    """One explicit saved Email per exact scenario version; no temporary drafts."""

    __tablename__ = "email_materials"
    __table_args__ = (
        CheckConstraint(
            "revision > 0 AND scenario_revision > 0", name="email_revision"
        ),
        CheckConstraint("schema_version = 'email-draft-v2'", name="email_schema"),
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("scenario_versions.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    scenario_revision: Mapped[int] = mapped_column(Integer)
    source_digest: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(40))
    context: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime())
    updated_at: Mapped[datetime] = mapped_column(DateTime())


class WebMaterial(Base):
    """One canonical component draft per exact scenario version."""

    __tablename__ = "web_materials"
    __table_args__ = (
        CheckConstraint(
            "revision > 0 AND scenario_revision > 0 AND email_revision > 0",
            name="web_revision",
        ),
        CheckConstraint("schema_version = 'web-draft-v3'", name="web_schema"),
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("scenario_versions.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    scenario_revision: Mapped[int] = mapped_column(Integer)
    email_revision: Mapped[int] = mapped_column(Integer)
    email_digest: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime())
    updated_at: Mapped[datetime] = mapped_column(DateTime())


class ScenarioLinkRecord(Base):
    __tablename__ = "scenario_links"
    __table_args__ = (CheckConstraint("revision > 0", name="link_revision"),)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("scenario_versions.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)


class RubricDefinitionRecord(Base):
    __tablename__ = "rubric_definitions"
    __table_args__ = (CheckConstraint("revision > 0", name="rubric_revision"),)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("scenario_versions.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)


class PublicationReview(Base):
    __tablename__ = "publication_reviews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("scenario_versions.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class ScenarioPublication(Base):
    __tablename__ = "scenario_publications"
    __table_args__ = {"sqlite_autoincrement": True}
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("scenario_versions.id"), unique=True
    )
    confirmation_id: Mapped[str] = mapped_column(
        ForeignKey("publication_reviews.id"), unique=True
    )
    publisher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime] = mapped_column(DateTime())
    manifest_digest: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict] = mapped_column(JSON)


class PublicationGroup(Base):
    __tablename__ = "publication_groups"
    __table_args__ = (CheckConstraint("revision > 0", name="grant_revision"),)
    publication_id: Mapped[int] = mapped_column(
        ForeignKey("scenario_publications.id"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("learning_groups.id"), primary_key=True
    )
    active: Mapped[bool] = mapped_column(Boolean)
    revision: Mapped[int] = mapped_column(Integer)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime())


class PublicationGrantAuditEvent(Base):
    __tablename__ = "publication_grant_audit"
    __table_args__ = (
        UniqueConstraint(
            "publication_id", "group_id", "grant_revision", name="grant_audit_revision"
        ),
        CheckConstraint("operation IN ('grant','revoke')", name="grant_operation"),
        CheckConstraint(
            "previous_active != new_active AND grant_revision > 0",
            name="grant_transition",
        ),
        {"sqlite_autoincrement": True},
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("scenario_publications.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("learning_groups.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(10))
    occurred_at: Mapped[datetime] = mapped_column(DateTime())
    previous_active: Mapped[bool] = mapped_column(Boolean)
    new_active: Mapped[bool] = mapped_column(Boolean)
    grant_revision: Mapped[int] = mapped_column(Integer)


class ScenarioAttemptRecord(Base):
    __tablename__ = "scenario_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('IN_PROGRESS','COMPLETED','ABANDONED')", name="attempt_status"
        ),
        CheckConstraint("current_stage IN ('EMAIL','WEB')", name="attempt_stage"),
        CheckConstraint(
            "decision IN ('NONE','DECLINED','LEFT')", name="attempt_decision"
        ),
        CheckConstraint(
            "revision > 0 AND last_event_sequence >= 0 AND scenario_version > 0",
            name="attempt_revision",
        ),
        CheckConstraint(
            (
                "(status = 'COMPLETED') = (completed_at IS NOT NULL) AND (status "
                "= 'ABANDONED') = (abandoned_at IS NOT NULL)"
            ),
            name="attempt_terminal_time",
        ),
        CheckConstraint(
            (
                "(completed_at IS NULL OR completed_at >= started_at) AND "
                "(abandoned_at IS NULL OR abandoned_at >= started_at)"
            ),
            name="attempt_time_order",
        ),
        CheckConstraint(
            "current_stage = 'WEB' OR web_visited = 0", name="attempt_visit"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    publication_id: Mapped[int] = mapped_column(ForeignKey("scenario_publications.id"))
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"))
    scenario_version: Mapped[int] = mapped_column(Integer)
    manifest_digest: Mapped[str] = mapped_column(String(64))
    authorization_group_id: Mapped[int] = mapped_column(
        ForeignKey("learning_groups.id")
    )
    scenario_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    current_stage: Mapped[str] = mapped_column(String(10))
    email_opened: Mapped[bool] = mapped_column(Boolean)
    decision: Mapped[str] = mapped_column(String(10))
    web_visited: Mapped[bool] = mapped_column(Boolean)
    started_at: Mapped[datetime] = mapped_column(DateTime())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime())
    revision: Mapped[int] = mapped_column(Integer)
    last_event_sequence: Mapped[int] = mapped_column(Integer)


class AttemptEventRecord(Base):
    __tablename__ = "attempt_events"
    __table_args__ = (
        UniqueConstraint("attempt_id", "sequence", name="attempt_event_sequence"),
        UniqueConstraint(
            "attempt_id", "request_id", "operation_index", name="attempt_event_request"
        ),
        CheckConstraint(
            "sequence > 0 AND operation_index BETWEEN 0 AND 2", name="event_order"
        ),
        CheckConstraint(
            "surface IN ('email','transition','web','system')", name="event_surface"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("scenario_attempts.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    surface: Mapped[str] = mapped_column(String(12))
    action_id: Mapped[str] = mapped_column(String(32))
    component_id: Mapped[str | None] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime())
    request_id: Mapped[str] = mapped_column(String(36))
    operation_digest: Mapped[str] = mapped_column(String(64))
    operation_index: Mapped[int] = mapped_column(Integer)


# Kept with metadata so migration parity detects accidental schema drift.
from sqlalchemy import Index, text  # noqa: E402

Index(
    "uq_active_learner_scenario",
    ScenarioAttemptRecord.learner_id,
    ScenarioAttemptRecord.scenario_id,
    unique=True,
    sqlite_where=text("status = 'IN_PROGRESS'"),
)
Index(
    "ix_attempt_learner_started",
    ScenarioAttemptRecord.learner_id,
    ScenarioAttemptRecord.started_at,
)
Index("ix_attempt_scenario", ScenarioAttemptRecord.scenario_id)
Index("ix_attempt_publication", ScenarioAttemptRecord.publication_id)
