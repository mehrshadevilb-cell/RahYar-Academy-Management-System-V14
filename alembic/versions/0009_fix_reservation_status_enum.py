"""Normalize reservationstatus enum labels to Python enum member names.

Revision ID: 0009
Revises: 0008

PostgreSQL requires ALTER TYPE ... ADD VALUE to be committed before a newly
added enum value can be used. Therefore enum additions are executed in an
Alembic autocommit block, followed by the data conversion in the normal
transaction.
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
    # PostgreSQL does not allow a newly-added enum label to be used in the
    # same transaction. Commit each ALTER TYPE block before converting rows.
    for label in _LABELS:
        escaped = label.replace("'", "''")
        with op.get_context().autocommit_block():
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

    # Now that all canonical labels have been committed, normalize existing
    # rows created with the previous lowercase labels.
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
