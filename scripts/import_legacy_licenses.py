"""
Imports pre-bot student records exported from the SpotPlayer panel
(licenses-*.xlsx) into RahYar's database.

Why this exists
----------------
Before the Telegram bot existed, students were registered directly in
SpotPlayer. This script brings that history into RahYar as:

  - a `User` row (full_name + phone), WITHOUT a `TelegramAccount` - the
    student hasn't started the bot yet, so there's nothing to link to.
    The first time they register through the bot with this same phone
    number, `LegacyImportService` (used in the registration handler)
    automatically moves this history onto their real account.
  - an `Enrollment` row per recognized product, so "دوره‌های من" shows
    the course once their account is linked.
  - a `License` row per recognized product, carrying over the existing
    SpotPlayer license key/id so support requests can be cross-checked
    against it. No new SpotPlayer API calls are made - the already
    -issued key is simply recorded (status="delivered").

No `Payment` rows are created: there is no real receipt to review for
these historical purchases, and inventing one would misrepresent the
academy's manual-payment-review audit trail.

Course name mapping
--------------------
The Excel `course` column contains free-text SpotPlayer course names,
which do NOT necessarily match RahYar's `Course.title` values exactly.
To avoid silently mis-granting access, only names in COURSE_NAME_MAP
below are imported; anything else is reported as a warning and
skipped (the user row is still created/updated). Extend the map and
re-run - the whole script is idempotent (safe to run multiple times).

Usage
-----
    pip install openpyxl --break-system-packages   # not a bot runtime dependency
    PYTHONPATH=. python scripts/import_legacy_licenses.py /path/to/licenses.xlsx [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys

import openpyxl

from src.database.session import SessionLocal
from src.database.models.user import User, UserRole
from src.database.models.course import Course
from src.database.models.enrollment import Enrollment
from src.database.models.license import License

PHONE_PATTERN = re.compile(r"^09\d{9}$")

# Excel course name -> RahYar Course.title
# Confirm/extend this before relying on the import for access control.
COURSE_NAME_MAP: dict[str, str] = {
    "تئوری موسیقی": "تئوری موسیقی",
    # "راه‌یار پرو": "راه‌یار",
    # "راه‌یار ِ تنظیم، میکس و مسترینگ": "راه‌یار",
    # "کیوبیس - Cubase (مهرشاد بنائی)": None,  # no matching product yet
}


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None

    digits = re.sub(r"\D", "", str(raw))

    if digits.startswith("98"):
        digits = "0" + digits[2:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits

    return digits if PHONE_PATTERN.match(digits) else None


def get_or_create_user(db, full_name: str, phone: str) -> tuple[User, bool]:
    user = db.query(User).filter(User.phone == phone).first()

    if user:
        return user, False

    user = User(
        full_name=full_name or "بدون نام",
        phone=phone,
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add(user)
    db.flush()

    return user, True


def get_or_create_enrollment(db, user_id: int, course_id: int) -> bool:
    existing = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user_id, Enrollment.course_id == course_id)
        .first()
    )
    if existing:
        return False

    db.add(Enrollment(user_id=user_id, course_id=course_id))
    return True


def get_or_create_license(
    db,
    user_id: int,
    product_id: int,
    spotplayer_license_id: str,
    license_key: str | None,
    created_at,
) -> bool:
    existing = (
        db.query(License)
        .filter(License.spotplayer_license_id == spotplayer_license_id)
        .first()
    )
    if existing:
        return False

    db.add(
        License(
            user_id=user_id,
            product_id=product_id,
            spotplayer_license_id=spotplayer_license_id,
            license_key=license_key,
            status="delivered",
            created_at=created_at,
        )
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx_path")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no DB writes")
    args = parser.parse_args()

    wb = openpyxl.load_workbook(args.xlsx_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() for h in rows[0]]

    col = {name: idx for idx, name in enumerate(header)}
    required = ["_id", "name", "course", "watermark", "key"]
    missing = [c for c in required if c not in col]
    if missing:
        print(f"❌ Missing expected columns: {missing}")
        sys.exit(1)

    db = SessionLocal()

    course_cache: dict[str, Course | None] = {}

    def resolve_course(title: str) -> Course | None:
        if title not in course_cache:
            course_cache[title] = (
                db.query(Course).filter(Course.title == title).first()
            )
        return course_cache[title]

    stats = {
        "rows": 0,
        "users_created": 0,
        "users_matched": 0,
        "skipped_no_phone": 0,
        "enrollments_created": 0,
        "licenses_created": 0,
        "unmapped_course_names": set(),
    }

    for row in rows[1:]:
        if not any(row):
            continue

        stats["rows"] += 1

        spotplayer_id = row[col["_id"]]
        name = (row[col["name"]] or "").strip() if row[col["name"]] else ""
        course_field = row[col["course"]] or ""
        phone = normalize_phone(row[col["watermark"]])
        license_key = row[col["key"]]
        created_at = row[col["create"]] if "create" in col else None

        if not phone:
            stats["skipped_no_phone"] += 1
            print(f"⚠️  Skipped row (no valid phone): name={name!r} watermark={row[col['watermark']]!r}")
            continue

        user, created = get_or_create_user(db, name, phone)
        stats["users_created" if created else "users_matched"] += 1

        course_names = [c.strip() for c in course_field.split(",") if c.strip()]

        matched_any_license = False

        for excel_course_name in course_names:
            mapped_title = COURSE_NAME_MAP.get(excel_course_name)

            if not mapped_title:
                stats["unmapped_course_names"].add(excel_course_name)
                continue

            course = resolve_course(mapped_title)
            if not course:
                print(f"⚠️  Mapped title {mapped_title!r} not found in courses table, skipping.")
                continue

            if get_or_create_enrollment(db, user.id, course.id):
                stats["enrollments_created"] += 1

            if get_or_create_license(
                db,
                user_id=user.id,
                product_id=course.id,
                spotplayer_license_id=str(spotplayer_id),
                license_key=license_key,
                created_at=created_at,
            ):
                stats["licenses_created"] += 1

            matched_any_license = True

        if not matched_any_license and course_names:
            pass  # already recorded in unmapped_course_names

    if args.dry_run:
        db.rollback()
        print("\n🔎 DRY RUN - no changes were committed.")
    else:
        db.commit()

    print("\n--- Import summary ---")
    print(f"Rows processed:        {stats['rows']}")
    print(f"Users created:         {stats['users_created']}")
    print(f"Users already existed: {stats['users_matched']}")
    print(f"Skipped (no phone):    {stats['skipped_no_phone']}")
    print(f"Enrollments created:   {stats['enrollments_created']}")
    print(f"Licenses created:      {stats['licenses_created']}")
    if stats["unmapped_course_names"]:
        print("\n⚠️  Unmapped course names (add them to COURSE_NAME_MAP and re-run):")
        for n in sorted(stats["unmapped_course_names"]):
            print(f"   - {n!r}")


if __name__ == "__main__":
    main()
