"""add assignments and assignment_submissions

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14

Depends on support_requests migration 0004. Merge support PR before this one.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.drop_index("ix_assignment_submissions_status", table_name="assignment_submissions")
    op.drop_index("ix_assignment_submissions_user_id", table_name="assignment_submissions")
    op.drop_index("ix_assignment_submissions_assignment_id", table_name="assignment_submissions")
    op.drop_index("ix_assignment_submissions_id", table_name="assignment_submissions")
    op.drop_table("assignment_submissions")
    op.drop_index("ix_assignments_online_course_id", table_name="assignments")
    op.drop_index("ix_assignments_id", table_name="assignments")
    op.drop_table("assignments")
    sa.Enum(name="submissionstatus").drop(op.get_bind(), checkfirst=True)
