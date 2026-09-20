#!/usr/bin/env python3
"""Production-safe Alembic bootstrap for Render.

Problem we hit repeatedly:
  - Production Postgres already has the full schema (tables + enums) from older
    create_all / partial deploys.
  - alembic_version is empty, so `alembic upgrade head` re-runs every migration
    from 0001 and dies on DuplicateTable / DuplicateObject.

Strategy:
  1. If core table `users` exists AND alembic has no current revision →
     stamp to head (schema is already adopted).
  2. Always run `alembic upgrade head` afterward so any *new* revisions still apply.
  3. App-side schema_guard still self-heals a few critical columns on boot.

This is intentionally conservative: only stamps when the DB looks pre-populated
and Alembic has never been initialized on that database.
"""
from __future__ import annotations

import subprocess
import sys

from sqlalchemy import create_engine, inspect, text

from src.core.config.settings import get_settings


def _alembic(*args: str) -> None:
    cmd = [sys.executable, "-m", "alembic", *args]
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def _needs_stamp(url: str) -> bool:
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            if "users" not in tables:
                # Fresh database — normal upgrade path from empty.
                print("migrate_boot: fresh DB (no users table) → upgrade only", flush=True)
                return False

            if "alembic_version" not in tables:
                print("migrate_boot: existing schema, no alembic_version → stamp head", flush=True)
                return True

            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            if row is None:
                print("migrate_boot: empty alembic_version → stamp head", flush=True)
                return True

            print(f"migrate_boot: already at revision {row[0]} → upgrade only", flush=True)
            return False
    finally:
        engine.dispose()


def main() -> int:
    settings = get_settings()
    url = settings.DATABASE_URL
    if not url:
        print("migrate_boot: DATABASE_URL is empty", file=sys.stderr, flush=True)
        return 1

    try:
        if _needs_stamp(url):
            _alembic("stamp", "head")
        _alembic("upgrade", "head")
    except subprocess.CalledProcessError as exc:
        print(f"migrate_boot: alembic failed with exit {exc.returncode}", file=sys.stderr, flush=True)
        return exc.returncode or 1
    except Exception as exc:
        print(f"migrate_boot: unexpected error: {exc}", file=sys.stderr, flush=True)
        return 1

    print("migrate_boot: ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
