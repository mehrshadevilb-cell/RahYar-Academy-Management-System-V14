"""add shared class inquiries for canonical users

Revision ID: 0018
Revises: 0017

Idempotent: adopt existing class_inquiries / classinquirystatus from older
create_all deployments instead of failing with DuplicateObject / DuplicateTable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = (
    ("ix_class_inquiries_id", ["id"]),
    ("ix_class_inquiries_user_id", ["user_id"]),
    ("ix_class_inquiries_online_course_id", ["online_course_id"]),
    ("ix_class_inquiries_status", ["status"]),
    ("ix_class_inquiries_user_status", ["user_id", "status"]),
    ("ix_class_inquiries_course_status", ["online_course_id", "status"]),
)


def _ensure_enum_pg(bind) -> None:
    bind.execute(
        text(
            """
            DO $$
            BEGIN
                CREATE TYPE classinquirystatus AS ENUM (
                    'PENDING', 'REVIEWING', 'APPROVED', 'REJECTED', 'ENROLLED'
                );
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())

    if "class_inquiries" not in tables:
        if bind.dialect.name == "postgresql":
            _ensure_enum_pg(bind)
            bind.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS class_inquiries (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        online_course_id INTEGER NOT NULL REFERENCES online_courses(id),
                        source VARCHAR(30) NOT NULL DEFAULT 'website',
                        requested_plan VARCHAR(30),
                        message TEXT,
                        status classinquirystatus NOT NULL DEFAULT 'PENDING',
                        reviewed_by_telegram_id VARCHAR(50),
                        review_note TEXT,
                        created_at TIMESTAMP WITHOUT TIME ZONE,
                        updated_at TIMESTAMP WITHOUT TIME ZONE
                    )
                    """
                )
            )
        else:
            op.create_table(
                "class_inquiries",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                sa.Column("online_course_id", sa.Integer(), sa.ForeignKey("online_courses.id"), nullable=False),
                sa.Column("source", sa.String(length=30), nullable=False, server_default="website"),
                sa.Column("requested_plan", sa.String(length=30), nullable=True),
                sa.Column("message", sa.Text(), nullable=True),
                sa.Column(
                    "status",
                    sa.Enum(
                        "PENDING",
                        "REVIEWING",
                        "APPROVED",
                        "REJECTED",
                        "ENROLLED",
                        name="classinquirystatus",
                    ),
                    nullable=False,
                    server_default="PENDING",
                ),
                sa.Column("reviewed_by_telegram_id", sa.String(length=50), nullable=True),
                sa.Column("review_note", sa.Text(), nullable=True),
                sa.Column("created_at", sa.DateTime(), nullable=True),
                sa.Column("updated_at", sa.DateTime(), nullable=True),
            )

    existing = {item["name"] for item in inspect(bind).get_indexes("class_inquiries")}
    for name, columns in _INDEXES:
        if name not in existing:
            op.create_index(name, "class_inquiries", columns)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "class_inquiries" not in tables:
        return
    existing = {item["name"] for item in inspect(bind).get_indexes("class_inquiries")}
    for name, _ in reversed(_INDEXES):
        if name in existing:
            op.drop_index(name, table_name="class_inquiries")
    op.drop_table("class_inquiries")
    if bind.dialect.name == "postgresql":
        sa.Enum(name="classinquirystatus").drop(bind, checkfirst=True)
