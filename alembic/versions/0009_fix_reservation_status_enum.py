"""Normalize reservationstatus enum labels to Python enum member names.

Revision ID: 0009
Revises: 0008

PostgreSQL 12+ allows ALTER TYPE ... ADD VALUE inside a transaction and
immediately using the new label. Avoid Alembic autocommit_block() which
asserts on _transaction and crashes under our env.py + psycopg3 setup on
Render (AssertionError: self._transaction is not None).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LABELS = (
    "WAITING_PAYMENT",
    "PAYMENT_SUBMITTED",
    "PENDING",
    "CONFIRMED",
    "REJECTED",
    "CANCELLED",
    "COMPLETED",
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # SQLite stores this enum as text and cannot execute PostgreSQL DO/
        # ALTER TYPE statements. The labels are already representable there.
        return

    for label in _LABELS:
        escaped = label.replace("'", "''")
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'reservationstatus'
                      AND e.enumlabel = '{escaped}'
                ) THEN
                    ALTER TYPE reservationstatus ADD VALUE '{escaped}';
                END IF;
            END
            $$;
            """
        )

    # Canonical labels are available in this same transaction on PG 12+.
    op.execute(
        """
        UPDATE reservations
        SET status = CASE status::text
            WHEN 'waiting_payment' THEN 'WAITING_PAYMENT'::reservationstatus
            WHEN 'payment_submitted' THEN 'PAYMENT_SUBMITTED'::reservationstatus
            WHEN 'pending' THEN 'PENDING'::reservationstatus
            WHEN 'confirmed' THEN 'CONFIRMED'::reservationstatus
            WHEN 'rejected' THEN 'REJECTED'::reservationstatus
            WHEN 'cancelled' THEN 'CANCELLED'::reservationstatus
            WHEN 'completed' THEN 'COMPLETED'::reservationstatus
            ELSE status
        END
        WHERE status::text IN (
            'waiting_payment', 'payment_submitted', 'pending', 'confirmed',
            'rejected', 'cancelled', 'completed'
        );
        """
    )


def downgrade() -> None:
    # PostgreSQL cannot safely remove enum labels without rebuilding the type.
    # Keep the canonical labels to avoid destructive schema changes.
    pass
