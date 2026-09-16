"""Idempotent schema repairs for critical production columns.

Alembic remains the source of truth for intentional schema changes. This module
exists only as a last-resort self-heal when a production database was stamped
to a revision that never actually applied a column (branched heads, partial
deploys, or a failed upgrade that still left the process running).

Keep this list short. Prefer real Alembic migrations for new work.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from src.database.connection import engine

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
        for table, column, ddl in _CRITICAL_COLUMNS:
            if dialect == "postgresql":
                # PostgreSQL 9.1+ supports IF NOT EXISTS on ADD COLUMN.
                sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"
                conn.execute(text(sql))
                logger.info("schema_guard: ensured %s.%s", table, column)
            else:
                # SQLite / other: inspect then add if missing.
                rows = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = :table AND column_name = :column"
                    ),
                    {"table": table, "column": column},
                ).fetchone()
                if rows is None:
                    # information_schema may not exist on pure SQLite; try PRAGMA.
                    try:
                        existing = {
                            r[1]
                            for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                        }
                    except Exception:
                        existing = set()
                    if column not in existing:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                        logger.info("schema_guard: added %s.%s", table, column)
