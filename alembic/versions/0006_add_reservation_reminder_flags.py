"""add reservation reminder flags

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-14

Quizzes/exams skipped; this follows assignments (0005).
Idempotent on PostgreSQL so partial deploys can recover.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("reservations", "reminder_1d_sent"):
        op.add_column(
            "reservations",
            sa.Column(
                "reminder_1d_sent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not _has_column("reservations", "reminder_due_sent"):
        op.add_column(
            "reservations",
            sa.Column(
                "reminder_due_sent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    if _has_column("reservations", "reminder_due_sent"):
        op.drop_column("reservations", "reminder_due_sent")
    if _has_column("reservations", "reminder_1d_sent"):
        op.drop_column("reservations", "reminder_1d_sent")
