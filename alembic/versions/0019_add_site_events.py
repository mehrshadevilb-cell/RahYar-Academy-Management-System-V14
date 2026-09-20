"""add privacy-preserving site analytics events

Revision ID: 0019
Revises: 0018

Idempotent for databases that already have site_events.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ("ix_site_events_id", ["id"]),
    ("ix_site_events_event_type", ["event_type"]),
    ("ix_site_events_visitor_hash", ["visitor_hash"]),
    ("ix_site_events_created_at", ["created_at"]),
    ("ix_site_events_type_created", ["event_type", "created_at"]),
    ("ix_site_events_path_created", ["path", "created_at"]),
)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if "site_events" not in tables:
        op.create_table(
            "site_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("path", sa.String(length=240), nullable=False, server_default="/"),
            sa.Column("visitor_hash", sa.String(length=64), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    existing = {item["name"] for item in inspect(bind).get_indexes("site_events")}
    for name, columns in _INDEXES:
        if name not in existing:
            op.create_index(name, "site_events", columns)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "site_events" not in tables:
        return
    existing = {item["name"] for item in inspect(bind).get_indexes("site_events")}
    for name, _ in reversed(_INDEXES):
        if name in existing:
            op.drop_index(name, table_name="site_events")
    op.drop_table("site_events")
