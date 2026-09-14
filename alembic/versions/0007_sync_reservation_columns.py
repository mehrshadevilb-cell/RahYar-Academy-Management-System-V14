"""sync missing reservation columns on production DBs

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-15

Older production databases were created before payment_proof / admin_notes
existed on the ORM model. This migration adds any missing columns
idempotently so the reminder scheduler and reservation queries stop
failing with UndefinedColumn.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("reservations", "payment_proof"):
        op.add_column(
            "reservations",
            sa.Column("payment_proof", sa.String(length=500), nullable=True),
        )
    if not _has_column("reservations", "admin_notes"):
        op.add_column(
            "reservations",
            sa.Column("admin_notes", sa.String(length=500), nullable=True),
        )
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
    # Do not drop columns that may hold production data.
    pass
