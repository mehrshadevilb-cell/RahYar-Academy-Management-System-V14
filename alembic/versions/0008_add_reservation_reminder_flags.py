"""add reservation reminder flags

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-14

Merge after: support 0004 → assignments 0005 → quizzes 0006 → exams 0007.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
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
