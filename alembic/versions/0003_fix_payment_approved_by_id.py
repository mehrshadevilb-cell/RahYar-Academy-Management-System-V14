"""fix payments.approved_by_id: drop wrong FK, widen to BIGINT

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12

This fixes a real production bug: `approved_by_id` was declared as
`ForeignKey("users.id")`, but `PaymentService.approve()/reject()` has
always stored the *admin's raw Telegram user id* there (see
`payment_service.py`), not an internal `users.id` row. On Postgres this
caused two problems that a SQLite dev database never surfaces (SQLite
doesn't enforce column-width limits or FK constraints the same way):

1. `NumericValueOutOfRange` - real Telegram ids (e.g. 8234306902)
   don't fit in a 32-bit INTEGER column.
2. Even after widening the type alone, the FK constraint would still
   reject it, since no `users.id` row equal to that Telegram id exists.

The constraint name is looked up dynamically rather than hard-coded,
since it's an unnamed FK and Postgres's auto-generated name can vary
depending on how the table was originally created.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for fk in inspector.get_foreign_keys("payments"):
        if fk.get("constrained_columns") == ["approved_by_id"] and fk.get("name"):
            op.drop_constraint(fk["name"], "payments", type_="foreignkey")

    op.alter_column(
        "payments",
        "approved_by_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Best-effort only: if any row already holds a Telegram id wider
    # than 32 bits, or one that doesn't match a real users.id, this
    # will fail - which is expected, since that data is exactly what
    # this migration exists to make valid.
    op.alter_column(
        "payments",
        "approved_by_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.create_foreign_key(
        "payments_approved_by_id_fkey",
        "payments",
        "users",
        ["approved_by_id"],
        ["id"],
    )
