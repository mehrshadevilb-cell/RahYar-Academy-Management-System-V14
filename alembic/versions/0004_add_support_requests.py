"""add support_requests table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("telegram_id", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "answered", "closed", name="supportstatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("admin_reply", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_support_requests_id", "support_requests", ["id"])
    op.create_index("ix_support_requests_user_id", "support_requests", ["user_id"])
    op.create_index("ix_support_requests_telegram_id", "support_requests", ["telegram_id"])
    op.create_index("ix_support_requests_status", "support_requests", ["status"])
    op.create_index("ix_support_requests_created_at", "support_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_support_requests_created_at", table_name="support_requests")
    op.drop_index("ix_support_requests_status", table_name="support_requests")
    op.drop_index("ix_support_requests_telegram_id", table_name="support_requests")
    op.drop_index("ix_support_requests_user_id", table_name="support_requests")
    op.drop_index("ix_support_requests_id", table_name="support_requests")
    op.drop_table("support_requests")
    sa.Enum(name="supportstatus").drop(op.get_bind(), checkfirst=True)
