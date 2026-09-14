"""add reservation reminder flags

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-14

Quizzes/exams skipped; this follows assignments (0005).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column(
            "reminder_1d_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
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
    op.drop_column("reservations", "reminder_due_sent")
    op.drop_column("reservations", "reminder_1d_sent")
