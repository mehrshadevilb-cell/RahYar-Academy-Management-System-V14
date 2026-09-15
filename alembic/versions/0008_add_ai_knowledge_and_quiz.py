"""Add AI knowledge ingestion and quiz storage.

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_index(name: str, table: str, columns: list[str]) -> None:
    inspector = inspect(op.get_bind())
    existing = {index["name"] for index in inspector.get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    # Importing src.database.models loads the complete model registry through
    # models/__init__.py, so current baseline databases already contain these
    # tables. Adopt them instead of raising DuplicateTable; create them only on
    # genuinely old deployments that predate the AI knowledge models.
    if "knowledge_items" not in tables:
        op.create_table(
            "knowledge_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_type", sa.String(30), nullable=False),
            sa.Column("source_key", sa.String(300), nullable=False),
            sa.Column("title", sa.String(500), nullable=True),
            sa.Column("source_url", sa.String(1000), nullable=True),
            sa.Column("language", sa.String(10), nullable=False, server_default="fa"),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("translated_text", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("tags", sa.String(1000), nullable=True),
            sa.Column("quiz_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("source_chat_id", sa.BigInteger(), nullable=True),
            sa.Column("source_message_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("source_type", "source_key", name="uq_knowledge_source_key"),
        )
        tables.add("knowledge_items")

    for name, columns in (
        ("ix_knowledge_items_source_type", ["source_type"]),
        ("ix_knowledge_items_source_key", ["source_key"]),
        ("ix_knowledge_items_created_at", ["created_at"]),
        ("ix_knowledge_items_quiz_ready", ["quiz_ready"]),
        ("ix_knowledge_items_source_chat_id", ["source_chat_id"]),
    ):
        _ensure_index(name, "knowledge_items", columns)

    if "quiz_questions" not in tables:
        op.create_table(
            "quiz_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("knowledge_item_id", sa.Integer(), nullable=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("option_a", sa.String(500), nullable=False),
            sa.Column("option_b", sa.String(500), nullable=False),
            sa.Column("option_c", sa.String(500), nullable=False),
            sa.Column("option_d", sa.String(500), nullable=False),
            sa.Column("correct_option", sa.Integer(), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        tables.add("quiz_questions")

    _ensure_index("ix_quiz_questions_knowledge_item_id", "quiz_questions", ["knowledge_item_id"])


def downgrade() -> None:
    # This migration can adopt tables that were created by the baseline/model
    # registry. Never destroy them during a historical downgrade; the baseline
    # owns the final schema teardown.
    return
