"""Idempotent schema repairs for critical production columns/tables."""
from __future__ import annotations

import logging

from sqlalchemy import text

from src.database.connection import engine

logger = logging.getLogger(__name__)

_CRITICAL_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("reservations", "reminder_1h_sent", "BOOLEAN NOT NULL DEFAULT false"),
    ("reservations", "reminder_1d_sent", "BOOLEAN NOT NULL DEFAULT false"),
    ("reservations", "reminder_due_sent", "BOOLEAN NOT NULL DEFAULT false"),
)

_MEMBER_PERSONALITY_PG = """
CREATE TABLE IF NOT EXISTS member_personality_profiles (
    id SERIAL PRIMARY KEY,
    telegram_id VARCHAR(50) NOT NULL UNIQUE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    display_name VARCHAR(120),
    message_count INTEGER NOT NULL DEFAULT 0,
    question_count INTEGER NOT NULL DEFAULT 0,
    help_count INTEGER NOT NULL DEFAULT 0,
    positive_count INTEGER NOT NULL DEFAULT 0,
    negative_count INTEGER NOT NULL DEFAULT 0,
    curiosity_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    helpfulness_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    politeness_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    engagement_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    interest_tags VARCHAR(500),
    summary_fa TEXT,
    recent_signals TEXT,
    last_message_at TIMESTAMP WITHOUT TIME ZONE,
    last_summary_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
)
"""

_MEMBER_PERSONALITY_SQLITE = """
CREATE TABLE IF NOT EXISTS member_personality_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id VARCHAR(50) NOT NULL UNIQUE,
    user_id INTEGER,
    display_name VARCHAR(120),
    message_count INTEGER NOT NULL DEFAULT 0,
    question_count INTEGER NOT NULL DEFAULT 0,
    help_count INTEGER NOT NULL DEFAULT 0,
    positive_count INTEGER NOT NULL DEFAULT 0,
    negative_count INTEGER NOT NULL DEFAULT 0,
    curiosity_score REAL NOT NULL DEFAULT 0,
    helpfulness_score REAL NOT NULL DEFAULT 0,
    politeness_score REAL NOT NULL DEFAULT 0.5,
    engagement_score REAL NOT NULL DEFAULT 0,
    interest_tags VARCHAR(500),
    summary_fa TEXT,
    recent_signals TEXT,
    last_message_at TIMESTAMP,
    last_summary_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def ensure_critical_schema() -> None:
    dialect = engine.dialect.name
    with engine.begin() as conn:
        for table, column, ddl in _CRITICAL_COLUMNS:
            if dialect == "postgresql":
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"))
                logger.info("schema_guard: ensured %s.%s", table, column)
            else:
                try:
                    existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
                except Exception:
                    existing = set()
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                    logger.info("schema_guard: added %s.%s", table, column)

        if dialect == "postgresql":
            conn.execute(text(_MEMBER_PERSONALITY_PG))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_member_personality_telegram_id ON member_personality_profiles (telegram_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_member_personality_user_id ON member_personality_profiles (user_id)"))
        else:
            conn.execute(text(_MEMBER_PERSONALITY_SQLITE))
        logger.info("schema_guard: ensured member_personality_profiles")
