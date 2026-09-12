"""add referrals table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "referrer_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "referred_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "rewarded", name="referralstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "reward_discount_code_id",
            sa.Integer(),
            sa.ForeignKey("discount_codes.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("rewarded_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("referrals")
