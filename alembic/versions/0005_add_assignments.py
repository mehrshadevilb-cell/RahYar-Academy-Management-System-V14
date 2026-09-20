"""add assignments and assignment_submissions

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14

Some production DBs already have these tables (from earlier create_all /
partial deploys) while alembic_version is still behind 0005. Adopt existing
tables instead of failing on DuplicateTable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ASSIGNMENT_INDEXES = (
    ("ix_assignments_id", ["id"]),
    ("ix_assignments_online_course_id", ["online_course_id"]),
)

_SUBMISSION_INDEXES = (
    ("ix_assignment_submissions_id", ["id"]),
    ("ix_assignment_submissions_assignment_id", ["assignment_id"]),
    ("ix_assignment_submissions_user_id", ["user_id"]),
    ("ix_assignment_submissions_status", ["status"]),
)


def _ensure_indexes(table: str, indexes: tuple[tuple[str, list[str]], ...]) -> None:
    existing = {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}
    for name, columns in indexes:
        if name not in existing:
            op.create_index(name, table, columns)


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

    _ensure_indexes("assignments", _ASSIGNMENT_INDEXES)

    if "assignment_submissions" not in inspect(bind).get_table_names():
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

    _ensure_indexes("assignment_submissions", _SUBMISSION_INDEXES)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "assignment_submissions" in tables:
        existing = {item["name"] for item in inspector.get_indexes("assignment_submissions")}
        for name, _ in reversed(_SUBMISSION_INDEXES):
            if name in existing:
                op.drop_index(name, table_name="assignment_submissions")
        op.drop_table("assignment_submissions")

    if "assignments" in tables:
        existing = {item["name"] for item in inspector.get_indexes("assignments")}
        for name, _ in reversed(_ASSIGNMENT_INDEXES):
            if name in existing:
                op.drop_index(name, table_name="assignments")
        op.drop_table("assignments")

    sa.Enum(name="submissionstatus").drop(bind, checkfirst=True)
