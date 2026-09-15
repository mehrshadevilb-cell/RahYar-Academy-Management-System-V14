"""add assignments and assignment_submissions

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14

The 0001 baseline already contains the current assignment ORM tables.
Keep this historical revision safe for upgrade paths where those tables
already exist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "assignments" not in tables:
        op.create_table(
            "assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("online_course_id", sa.Integer(), sa.ForeignKey("online_courses.id"), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_assignments_id", "assignments", ["id"])
        op.create_index("ix_assignments_online_course_id", "assignments", ["online_course_id"])

    if "assignment_submissions" not in tables:
        op.create_table(
            "assignment_submissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("pending", "reviewed", "returned", name="submissionstatus"),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("admin_feedback", sa.Text(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_assignment_submissions_id", "assignment_submissions", ["id"])
        op.create_index("ix_assignment_submissions_assignment_id", "assignment_submissions", ["assignment_id"])
        op.create_index("ix_assignment_submissions_user_id", "assignment_submissions", ["user_id"])
        op.create_index("ix_assignment_submissions_status", "assignment_submissions", ["status"])


def downgrade() -> None:
    # Baseline-owned tables must survive downgrades of historical revisions.
    return
