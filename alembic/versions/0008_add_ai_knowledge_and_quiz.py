"""Add AI knowledge ingestion and quiz storage.

Revision ID: 0008
Revises: 0007

Idempotent: adopt tables if they already exist from earlier create_all
or partial deploys so upgrade head does not crash on DuplicateTable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_indexes(table: str, indexes: list[tuple[str, list[str]]]) -> None:
    existing = {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}
    for name, columns in indexes:
        if name not in existing:
            op.create_index(name, table, columns)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

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

    _ensure_indexes(
        "knowledge_items",
        [
            ("ix_knowledge_items_source_type", ["source_type"]),
            ("ix_knowledge_items_source_key", ["source_key"]),
            ("ix_knowledge_items_created_at", ["created_at"]),
            ("ix_knowledge_items_quiz_ready", ["quiz_ready"]),
            ("ix_knowledge_items_source_chat_id", ["source_chat_id"]),
        ],
    )

    if "quiz_questions" not in inspect(bind).get_table_names():
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

    _ensure_indexes(
        "quiz_questions",
        [("ix_quiz_questions_knowledge_item_id", ["knowledge_item_id"])],
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "quiz_questions" in tables:
        existing = {item["name"] for item in inspect(bind).get_indexes("quiz_questions")}
        if "ix_quiz_questions_knowledge_item_id" in existing:
            op.drop_index("ix_quiz_questions_knowledge_item_id", table_name="quiz_questions")
        op.drop_table("quiz_questions")
    if "knowledge_items" in tables:
        existing = {item["name"] for item in inspect(bind).get_indexes("knowledge_items")}
        for name in (
            "ix_knowledge_items_source_chat_id",
            "ix_knowledge_items_quiz_ready",
            "ix_knowledge_items_created_at",
            "ix_knowledge_items_source_key",
            "ix_knowledge_items_source_type",
        ):
            if name in existing:
                op.drop_index(name, table_name="knowledge_items")
        op.drop_table("knowledge_items")
