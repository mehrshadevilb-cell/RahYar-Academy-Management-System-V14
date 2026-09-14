"""add reservation reminder flags

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-14

If other feature PRs already claimed 0004–0007, renumber this to the next
free revision (e.g. 0008) before merge.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
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
