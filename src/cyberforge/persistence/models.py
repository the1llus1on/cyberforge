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
