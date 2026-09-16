"""repair missing reservations.reminder_1h_sent column

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-16

Production (and some stamped) databases are missing reminder_1h_sent even
though the ORM model and class-reminder logic already expect it. 0013 added
the column for clean upgrade paths; this repair is idempotent so partial or
skipped upgrades recover without data loss.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("reservations", "reminder_1h_sent"):
        op.add_column(
            "reservations",
            sa.Column(
                "reminder_1h_sent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    # Non-destructive: keep the column if it holds production state.
    pass
