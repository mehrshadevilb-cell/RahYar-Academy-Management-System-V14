"""Idempotent schema repairs for critical production columns.

Alembic remains the source of truth for intentional schema changes. This module
exists only as a last-resort self-heal when a production database was stamped
to a revision that never actually applied a column (branched heads, partial
deploys, or a failed upgrade that still left the process running).

Keep this list short. Prefer real Alembic migrations for new work.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from src.database.connection import engine
from src.database.models.free_lesson import FreeLesson

logger = logging.getLogger(__name__)

# (table, column, DDL fragment after ADD COLUMN)
_CRITICAL_COLUMNS: tuple[tuple[str, str, str], ...] = (
    (
        "reservations",
        "reminder_1h_sent",
        "BOOLEAN NOT NULL DEFAULT false",
    ),
    (
        "reservations",
        "reminder_1d_sent",
        "BOOLEAN NOT NULL DEFAULT false",
    ),
    (
        "reservations",
        "reminder_due_sent",
        "BOOLEAN NOT NULL DEFAULT false",
    ),
)


def ensure_critical_schema() -> None:
    """Ensure critical columns exist. Safe to call on every process start."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        # Some early production databases were stamped after migration 0017
        # without the actual table.  `checkfirst` repairs only that incomplete
        # deployment and remains a no-op for correctly migrated databases.
        FreeLesson.__table__.create(bind=conn, checkfirst=True)
        logger.info("schema_guard: ensured free_lessons table")
        for table, column, ddl in _CRITICAL_COLUMNS:
            if dialect == "postgresql":
                # PostgreSQL 9.1+ supports IF NOT EXISTS on ADD COLUMN.
                sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"
                conn.execute(text(sql))
                logger.info("schema_guard: ensured %s.%s", table, column)
            else:
                existing = {
                    row["name"]
                    for row in inspect(conn).get_columns(table)
                }
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                    logger.info("schema_guard: added %s.%s", table, column)
