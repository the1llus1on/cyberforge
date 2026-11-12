"""Phase 2 storage only. No scenario or scoring tables."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
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
