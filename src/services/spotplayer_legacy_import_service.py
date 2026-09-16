"""Import historical SpotPlayer licenses into RahYar as legacy students.

Creates placeholder User rows (name + phone, no TelegramAccount) so the
existing LegacyImportService can merge purchase history when the student
later registers in the bot with the same phone.

Idempotent: re-running the same export does not duplicate enrollments or
licenses keyed by (spotplayer_license_id, product_id).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.database.models.course import Course
from src.database.models.enrollment import Enrollment
from src.database.models.license import License
from src.database.models.user import User, UserRole

# SpotPlayer course labels (export) -> bot Course.title values.
# Unmapped labels are reported and skipped; they never invent products.
DEFAULT_COURSE_MAP: dict[str, str] = {
    "تئوری موسیقی": "تئوری موسیقی",
    "راه‌یار ِ تنظیم، میکس و مسترینگ": "راه‌یار",
    "راه‌یار پرو": "راه‌یار",
    # Cubase is not in default seed products — leave unmapped unless owner adds it.
}


def normalize_iran_phone(raw: str | None) -> str | None:
    """Normalize common Iranian phone forms to 09xxxxxxxxx."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # Reject obvious non-phone watermarks (names, etc.).
    if re.search(r"[A-Za-zآ-ی]", text) and not re.search(r"\d", text):
        return None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if digits.startswith("98") and len(digits) >= 12:
        digits = "0" + digits[2:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    if len(digits) != 11 or not digits.startswith("09"):
        return None
    # Skip placeholder / fake numbers from test licenses.
    if digits in {"09000000000", "09111111111", "00000000000"}:
        return None
    return digits


@dataclass
class ImportRowResult:
    name: str
    phone: str | None
    spotplayer_id: str
    courses_raw: str
    status: str
    detail: str = ""


@dataclass
class ImportSummary:
    created_users: int = 0
    reused_users: int = 0
    created_enrollments: int = 0
    created_licenses: int = 0
    skipped: int = 0
    errors: int = 0
    rows: list[ImportRowResult] = field(default_factory=list)


class SpotPlayerLegacyImportService:
    """Import SpotPlayer XLSX/CSV-style rows into users + enrollments + licenses."""

    def __init__(self, course_map: dict[str, str] | None = None) -> None:
        self.course_map = dict(course_map or DEFAULT_COURSE_MAP)

    def _resolve_products(self, db: Session, course_cell: str) -> tuple[list[Course], list[str]]:
        labels = [part.strip() for part in str(course_cell or "").split(",") if part.strip()]
        products: list[Course] = []
        missing: list[str] = []
        seen_ids: set[int] = set()
        for label in labels:
            title = self.course_map.get(label)
            if not title:
                missing.append(label)
                continue
            product = db.query(Course).filter(Course.title == title).first()
            if not product:
                missing.append(f"{label}→{title} (product missing)")
                continue
            if product.id not in seen_ids:
                products.append(product)
                seen_ids.add(product.id)
        return products, missing

    def _get_or_create_user(self, db: Session, full_name: str, phone: str) -> tuple[User, bool]:
        existing = db.query(User).filter(User.phone == phone).first()
        if existing:
            if full_name and (not existing.full_name or len(existing.full_name) < 3):
                existing.full_name = full_name[:100]
            return existing, False
        user = User(
            full_name=(full_name or "هنرجوی اسپات‌پلیر")[:100],
            phone=phone,
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user, True

    def import_row(
        self,
        db: Session,
        *,
        name: str,
        watermark: str,
        course_cell: str,
        spotplayer_id: str,
        license_key: str,
        created_at: datetime | None = None,
        dry_run: bool = True,
    ) -> ImportRowResult:
        phone = normalize_iran_phone(watermark)
        if not phone:
            return ImportRowResult(
                name=name,
                phone=None,
                spotplayer_id=str(spotplayer_id or ""),
                courses_raw=str(course_cell or ""),
                status="skipped",
                detail="invalid or placeholder phone",
            )
        if not license_key or not spotplayer_id:
            return ImportRowResult(
                name=name,
                phone=phone,
                spotplayer_id=str(spotplayer_id or ""),
                courses_raw=str(course_cell or ""),
                status="skipped",
                detail="missing license key or SpotPlayer id",
            )

        products, missing = self._resolve_products(db, course_cell)
        if not products:
            return ImportRowResult(
                name=name,
                phone=phone,
                spotplayer_id=str(spotplayer_id),
                courses_raw=str(course_cell or ""),
                status="skipped",
                detail="no mapped products: " + ", ".join(missing) if missing else "empty courses",
            )

        if dry_run:
            detail = f"would import {len(products)} product(s)"
            if missing:
                detail += f"; unmapped={missing}"
            return ImportRowResult(
                name=name,
                phone=phone,
                spotplayer_id=str(spotplayer_id),
                courses_raw=str(course_cell or ""),
                status="dry_run",
                detail=detail,
            )

        user, created = self._get_or_create_user(db, name, phone)
        enroll_n = 0
        lic_n = 0
        for product in products:
            enrollment = (
                db.query(Enrollment)
                .filter(Enrollment.user_id == user.id, Enrollment.course_id == product.id)
                .first()
            )
            if not enrollment:
                enrollment = Enrollment(user_id=user.id, course_id=product.id)
                if created_at:
                    enrollment.created_at = created_at
                db.add(enrollment)
                enroll_n += 1

            existing_license = (
                db.query(License)
                .filter(
                    License.spotplayer_license_id == str(spotplayer_id),
                    License.product_id == product.id,
                )
                .first()
            )
            if existing_license:
                continue
            active = (
                db.query(License)
                .filter(
                    License.user_id == user.id,
                    License.product_id == product.id,
                    License.status == "active",
                )
                .first()
            )
            if active and active.license_key:
                continue

            license_row = License(
                user_id=user.id,
                product_id=product.id,
                payment_id=None,
                spotplayer_license_id=str(spotplayer_id),
                license_key=str(license_key),
                status="active",
            )
            if created_at:
                license_row.created_at = created_at
            db.add(license_row)
            lic_n += 1

        db.flush()
        detail = f"user={'created' if created else 'reused'}; enroll+={enroll_n}; license+={lic_n}"
        if missing:
            detail += f"; unmapped={missing}"
        return ImportRowResult(
            name=name,
            phone=phone,
            spotplayer_id=str(spotplayer_id),
            courses_raw=str(course_cell or ""),
            status="imported",
            detail=detail,
        )

    def import_xlsx(
        self,
        db: Session,
        path: Path,
        *,
        dry_run: bool = True,
        sheet_name: str | None = None,
    ) -> ImportSummary:
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openpyxl is required to import XLSX files") from exc

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet_name] if sheet_name else wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return ImportSummary()

        header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]

        def col(*names: str) -> int | None:
            for name in names:
                if name in header:
                    return header.index(name)
            return None

        idx_id = col("_id", "id")
        idx_name = col("name")
        idx_course = col("course", "courses")
        idx_watermark = col("watermark", "phone")
        idx_key = col("key", "license", "license_key")
        idx_create = col("create", "created", "created_at")
        if None in (idx_id, idx_name, idx_course, idx_watermark, idx_key):
            raise RuntimeError(f"Unexpected XLSX header: {header}")

        summary = ImportSummary()
        for raw in rows[1:]:
            if not raw or all(v is None or str(v).strip() == "" for v in raw):
                continue
            created_at = raw[idx_create] if idx_create is not None else None
            if created_at is not None and not isinstance(created_at, datetime):
                created_at = None
            result = self.import_row(
                db,
                name=str(raw[idx_name] or "").strip(),
                watermark=str(raw[idx_watermark] or "").strip(),
                course_cell=str(raw[idx_course] or ""),
                spotplayer_id=str(raw[idx_id] or "").strip(),
                license_key=str(raw[idx_key] or "").strip(),
                created_at=created_at,
                dry_run=dry_run,
            )
            summary.rows.append(result)
            if result.status == "imported":
                if "user=created" in result.detail:
                    summary.created_users += 1
                if "user=reused" in result.detail:
                    summary.reused_users += 1
                m_en = re.search(r"enroll\+=(\d+)", result.detail)
                m_lic = re.search(r"license\+=(\d+)", result.detail)
                if m_en:
                    summary.created_enrollments += int(m_en.group(1))
                if m_lic:
                    summary.created_licenses += int(m_lic.group(1))
            elif result.status in {"skipped", "dry_run"}:
                summary.skipped += 1
            else:
                summary.errors += 1

        if not dry_run:
            db.commit()
        return summary
