"""Users, learning groups, and role-specific many-to-many membership."""

import sqlalchemy as sa
from alembic import op

revision = "0001_users_groups"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("username_key", sa.String(80), nullable=False, unique=True),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "role IN ('administrator', 'instructor', 'learner')", name="user_role"
        ),
        sa.CheckConstraint("length(username) BETWEEN 1 AND 80", name="username_length"),
        sa.CheckConstraint(
            "length(display_name) BETWEEN 1 AND 160", name="display_name_length"
        ),
        sa.CheckConstraint(
            "password_hash LIKE '$argon2id$%'", name="password_argon2id"
        ),
    )
    op.create_table(
        "learning_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name="group_name_length"),
    )
    for table in ("group_instructors", "group_learners"):
        op.create_table(
            table,
            sa.Column(
                "group_id",
                sa.Integer(),
                sa.ForeignKey("learning_groups.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )
        role = "instructor" if table == "group_instructors" else "learner"
        for operation in ("INSERT", "UPDATE"):
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {table}_{operation.lower()}_role "
                    f"BEFORE {operation} ON {table} "
                    f"WHEN (SELECT role FROM users WHERE id=NEW.user_id) != '{role}' "
                    "BEGIN SELECT RAISE(ABORT, 'invalid membership role'); END"
                )
            )
    op.execute(
        sa.text(
            "CREATE TRIGGER users_membership_role BEFORE UPDATE OF role ON users "
            "WHEN (NEW.role != 'instructor' AND EXISTS (SELECT 1 FROM "
            "group_instructors WHERE user_id=NEW.id)) "
            "OR (NEW.role != 'learner' AND EXISTS (SELECT 1 FROM "
            "group_learners WHERE user_id=NEW.id)) "
            "BEGIN SELECT RAISE(ABORT, 'remove memberships before role change'); END"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER users_membership_role"))
    op.drop_table("group_learners")
    op.drop_table("group_instructors")
    op.drop_table("learning_groups")
    op.drop_table("users")
