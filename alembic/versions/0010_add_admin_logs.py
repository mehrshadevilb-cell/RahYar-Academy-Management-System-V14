"""Add append-only admin audit log table.

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_telegram_id", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_logs_id", "admin_logs", ["id"], unique=False)
    op.create_index("ix_admin_logs_admin_telegram_id", "admin_logs", ["admin_telegram_id"], unique=False)
    op.create_index("ix_admin_logs_action", "admin_logs", ["action"], unique=False)
    op.create_index("ix_admin_logs_created_at", "admin_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_logs_created_at", table_name="admin_logs")
    op.drop_index("ix_admin_logs_action", table_name="admin_logs")
    op.drop_index("ix_admin_logs_admin_telegram_id", table_name="admin_logs")
    op.drop_index("ix_admin_logs_id", table_name="admin_logs")
    op.drop_table("admin_logs")
