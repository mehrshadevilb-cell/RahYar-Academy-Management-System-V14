"""ensure reservations.reminder_1h_sent via IF NOT EXISTS

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-16

Production still reports UndefinedColumn for reminder_1h_sent after 0013/0015.
This revision uses PostgreSQL ADD COLUMN IF NOT EXISTS so a stuck or partial
stamp still recovers on the next alembic upgrade head.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE reservations "
            "ADD COLUMN IF NOT EXISTS reminder_1h_sent BOOLEAN NOT NULL DEFAULT false"
        )
        op.execute(
            "ALTER TABLE reservations "
            "ADD COLUMN IF NOT EXISTS reminder_1d_sent BOOLEAN NOT NULL DEFAULT false"
        )
        op.execute(
            "ALTER TABLE reservations "
            "ADD COLUMN IF NOT EXISTS reminder_due_sent BOOLEAN NOT NULL DEFAULT false"
        )
    else:
        from sqlalchemy import inspect
        import sqlalchemy as sa

        cols = {c["name"] for c in inspect(bind).get_columns("reservations")}
        if "reminder_1h_sent" not in cols:
            op.add_column(
                "reservations",
                sa.Column("reminder_1h_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if "reminder_1d_sent" not in cols:
            op.add_column(
                "reservations",
                sa.Column("reminder_1d_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if "reminder_due_sent" not in cols:
            op.add_column(
                "reservations",
                sa.Column("reminder_due_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
            )


def downgrade() -> None:
    # Keep production data; do not drop reminder flags.
    pass
