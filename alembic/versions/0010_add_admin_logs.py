"""Add append-only admin audit log table.

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_index(name: str, table: str, columns: list[str]) -> None:
    inspector = inspect(op.get_bind())
    existing = {index["name"] for index in inspector.get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    # Some older deployments created this table with Base.metadata.create_all()
    # before Alembic became the sole schema owner. In that case the table already
    # exists while alembic_version is still 0009. Treat the existing table as the
    # 0010 schema and only add missing indexes.
    if "admin_logs" not in tables:
        op.create_table(
            "admin_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("admin_telegram_id", sa.String(length=50), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    _ensure_index("ix_admin_logs_id", "admin_logs", ["id"])
    _ensure_index("ix_admin_logs_admin_telegram_id", "admin_logs", ["admin_telegram_id"])
    _ensure_index("ix_admin_logs_action", "admin_logs", ["action"])
    _ensure_index("ix_admin_logs_created_at", "admin_logs", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "admin_logs" not in tables:
        return

    existing = {index["name"] for index in inspector.get_indexes("admin_logs")}
    for name in (
        "ix_admin_logs_created_at",
        "ix_admin_logs_action",
        "ix_admin_logs_admin_telegram_id",
        "ix_admin_logs_id",
    ):
        if name in existing:
            op.drop_index(name, table_name="admin_logs")
    op.drop_table("admin_logs")
