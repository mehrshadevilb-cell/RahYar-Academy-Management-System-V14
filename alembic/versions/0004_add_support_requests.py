"""add support_requests table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-14

The 0001 baseline already creates the current ORM schema, including
support_requests. This revision remains for databases that were stamped at
0003 before the baseline adoption, but must not recreate an existing table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ("ix_support_requests_id", ["id"]),
    ("ix_support_requests_user_id", ["user_id"]),
    ("ix_support_requests_telegram_id", ["telegram_id"]),
    ("ix_support_requests_status", ["status"]),
    ("ix_support_requests_created_at", ["created_at"]),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "support_requests" in inspector.get_table_names():
        # 0001 owns this table on fresh installs. Do not mutate or recreate it.
        return

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
    for name, columns in _INDEXES:
        op.create_index(name, "support_requests", columns)


def downgrade() -> None:
    # Never remove a table that belongs to the 0001 baseline.
    return
