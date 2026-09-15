"""Add AI knowledge ingestion and quiz storage.

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_index("ix_knowledge_items_source_type", "knowledge_items", ["source_type"])
    op.create_index("ix_knowledge_items_source_key", "knowledge_items", ["source_key"])
    op.create_index("ix_knowledge_items_created_at", "knowledge_items", ["created_at"])
    op.create_index("ix_knowledge_items_quiz_ready", "knowledge_items", ["quiz_ready"])
    op.create_index("ix_knowledge_items_source_chat_id", "knowledge_items", ["source_chat_id"])
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
    op.create_index("ix_quiz_questions_knowledge_item_id", "quiz_questions", ["knowledge_item_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_questions_knowledge_item_id", table_name="quiz_questions")
    op.drop_table("quiz_questions")
    op.drop_index("ix_knowledge_items_source_chat_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_quiz_ready", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_created_at", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_source_key", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_source_type", table_name="knowledge_items")
    op.drop_table("knowledge_items")
