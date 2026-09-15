"""add ai providers and models

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _ensure_index(name: str, table: str, columns: list[str], *, postgresql_where=None, sqlite_where=None) -> None:
    inspector = inspect(op.get_bind())
    existing = {index["name"] for index in inspector.get_indexes(table)}
    if name not in existing:
        op.create_index(
            name,
            table,
            columns,
            unique=False if name != "uq_ai_models_default_provider" else True,
            postgresql_where=postgresql_where,
            sqlite_where=sqlite_where,
        )


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    # Older deployments may have created these tables through Base.metadata.create_all()
    # before Alembic became the sole schema owner. Adopt existing tables instead of
    # failing with DuplicateTable, then ensure migration-specific indexes exist.
    if "ai_providers" not in tables:
        op.create_table(
            "ai_providers",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("display_name", sa.String(length=150), nullable=False),
            sa.Column("base_url", sa.String(length=500), nullable=False),
            sa.Column("api_key_encrypted", sa.Text(), nullable=False),
            sa.Column("provider_type", sa.String(length=50), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("supports_streaming", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("extra_config", json_type, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("last_models_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        tables.add("ai_providers")

    _ensure_index("ix_ai_providers_name", "ai_providers", ["name"])
    _ensure_index("ix_ai_providers_provider_type", "ai_providers", ["provider_type"])
    _ensure_index("ix_ai_providers_is_active", "ai_providers", ["is_active"])

    if "ai_models" not in tables:
        op.create_table(
            "ai_models",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("provider_id", sa.Uuid(), nullable=False),
            sa.Column("model_id", sa.String(length=200), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("context_window", sa.Integer(), nullable=True),
            sa.Column("max_output_tokens", sa.Integer(), nullable=True),
            sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("supports_streaming", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("pricing_input", sa.Numeric(18, 8), nullable=True),
            sa.Column("pricing_output", sa.Numeric(18, 8), nullable=True),
            sa.Column("raw_metadata", json_type, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
        )
        tables.add("ai_models")

    _ensure_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])
    _ensure_index("ix_ai_models_is_active", "ai_models", ["is_active"])
    _ensure_index(
        "uq_ai_models_default_provider",
        "ai_models",
        ["provider_id"],
        postgresql_where=sa.text("is_default = true"),
        sqlite_where=sa.text("is_default = 1"),
    )


def downgrade() -> None:
    # The upgrade can adopt pre-existing tables. Because migration history does not
    # persist whether a table was adopted or newly created, never drop these shared
    # tables on downgrade. This prevents an emergency downgrade from destroying data.
    bind = op.get_bind()
    inspector = inspect(bind)
    for table, indexes in (
        (
            "ai_models",
            ("uq_ai_models_default_provider", "ix_ai_models_is_active", "ix_ai_models_provider_id"),
        ),
        (
            "ai_providers",
            ("ix_ai_providers_is_active", "ix_ai_providers_provider_type", "ix_ai_providers_name"),
        ),
    ):
        if table not in inspector.get_table_names():
            continue
        existing = {index["name"] for index in inspector.get_indexes(table)}
        for name in indexes:
            if name in existing:
                op.drop_index(name, table_name=table)
