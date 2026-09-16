#!/usr/bin/env python3
"""CLI: import SpotPlayer license export into RahYar (legacy users by name+phone).

Usage:
  python scripts/import_spotplayer_licenses.py path/to/licenses.xlsx --dry-run
  python scripts/import_spotplayer_licenses.py path/to/licenses.xlsx --apply

Requires DATABASE_URL in the environment (same as the bot).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.session import SessionLocal
from src.services.spotplayer_legacy_import_service import SpotPlayerLegacyImportService


def main() -> int:
    parser = argparse.ArgumentParser(description="Import SpotPlayer licenses as legacy RahYar students")
    parser.add_argument("xlsx", type=Path, help="Path to SpotPlayer licenses XLSX export")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Validate only; no DB writes")
    group.add_argument("--apply", action="store_true", help="Write users/enrollments/licenses")
    args = parser.parse_args()

    if not args.xlsx.is_file():
        print(f"File not found: {args.xlsx}")
        return 2

    service = SpotPlayerLegacyImportService()
    db = SessionLocal()
    try:
        summary = service.import_xlsx(db, args.xlsx, dry_run=not args.apply)
    finally:
        db.close()

    mode = "DRY-RUN" if not args.apply else "APPLY"
    print(f"=== SpotPlayer legacy import ({mode}) ===")
    print(f"rows={len(summary.rows)} created_users={summary.created_users} reused_users={summary.reused_users}")
    print(f"enrollments+={summary.created_enrollments} licenses+={summary.created_licenses} skipped={summary.skipped}")
    for row in summary.rows:
        print(f"[{row.status}] {row.name} | {row.phone} | {row.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
