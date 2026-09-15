"""add support_requests table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-14
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
    tables = set(inspector.get_table_names())

    # Some older deployments created ORM tables before Alembic became the
    # schema owner. Adopt an existing table instead of crashing on restart.
    if "support_requests" not in tables:
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

    existing = {index["name"] for index in inspector.get_indexes("support_requests")}
    for name, columns in _INDEXES:
        if name not in existing:
            op.create_index(name, "support_requests", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "support_requests" not in inspector.get_table_names():
        return
    existing = {index["name"] for index in inspector.get_indexes("support_requests")}
    for name, _ in reversed(_INDEXES):
        if name in existing:
            op.drop_index(name, table_name="support_requests")
    op.drop_table("support_requests")
    sa.Enum(name="supportstatus").drop(bind, checkfirst=True)
