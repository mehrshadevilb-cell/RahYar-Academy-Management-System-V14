"""Normalize reservationstatus enum labels to Python enum member names.

Revision ID: 0009
Revises: 0008

The ORM now persists ReservationStatus member names (WAITING_PAYMENT,
PAYMENT_SUBMITTED, ...). Some production databases were created with the
older lowercase enum labels, which causes PostgreSQL InvalidTextRepresentation
when a new reservation is inserted. Add the canonical uppercase labels and
normalize existing rows without dropping the enum type.
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
    # Add canonical labels only when they are missing. This is safe whether
    # the existing database enum contains lowercase labels, uppercase labels,
    # or a mixture from previous deployments.
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

    # Convert rows created with the old lowercase labels to the canonical
    # labels expected by SQLAlchemy's ReservationStatus mapping.
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
    # PostgreSQL cannot safely remove enum labels while rows/types may depend
    # on them. Keep the canonical labels in place; the migration is therefore
    # intentionally data-preserving and has no destructive downgrade.
    pass
