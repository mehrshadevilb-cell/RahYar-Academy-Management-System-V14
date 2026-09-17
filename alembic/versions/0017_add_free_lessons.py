"""add editable free lessons

Revision ID: 0017
Revises: 0016
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "free_lessons" not in inspector.get_table_names():
        op.create_table(
            "free_lessons",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("duration_label", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("video_url", sa.String(length=500), nullable=True),
            sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
            sa.Column("chapters", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        inspector = inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("free_lessons")}
    if "ix_free_lessons_id" not in existing_indexes:
        op.create_index("ix_free_lessons_id", "free_lessons", ["id"])
    if "ix_free_lessons_slug" not in existing_indexes:
        op.create_index("ix_free_lessons_slug", "free_lessons", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_free_lessons_slug", table_name="free_lessons")
    op.drop_index("ix_free_lessons_id", table_name="free_lessons")
    op.drop_table("free_lessons")
