"""Admin student directory: Telegram users + legacy (no Telegram) imports."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from src.database.models.course import Course
from src.database.models.enrollment import Enrollment
from src.database.models.license import License
from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User, UserRole


class StudentFilter(str, Enum):
    ALL = "all"
    TELEGRAM = "tg"
    LEGACY = "legacy"


@dataclass(frozen=True)
class StudentListItem:
    user_id: int
    full_name: str
    phone: str | None
    has_telegram: bool
    is_active: bool
    enroll_count: int
    active_license_count: int


class StudentAdminService:
    PAGE_SIZE = 8

    def counts(self, db: Session) -> dict[str, int]:
        total = db.query(func.count(User.id)).filter(User.role == UserRole.STUDENT).scalar() or 0
        with_tg = (
            db.query(func.count(User.id))
            .join(TelegramAccount, TelegramAccount.user_id == User.id)
            .filter(User.role == UserRole.STUDENT)
            .scalar()
            or 0
        )
        return {
            "total": int(total),
            "telegram": int(with_tg),
            "legacy": int(total) - int(with_tg),
        }

    def _base_query(self, db: Session, filt: StudentFilter):
        q = db.query(User).filter(User.role == UserRole.STUDENT)
        if filt == StudentFilter.TELEGRAM:
            q = q.join(TelegramAccount, TelegramAccount.user_id == User.id)
        elif filt == StudentFilter.LEGACY:
            q = q.outerjoin(TelegramAccount, TelegramAccount.user_id == User.id).filter(
                TelegramAccount.id.is_(None)
            )
        return q

    def list_students(
        self,
        db: Session,
        *,
        filt: StudentFilter = StudentFilter.ALL,
        page: int = 0,
    ) -> tuple[list[StudentListItem], int]:
        page = max(0, page)
        base = self._base_query(db, filt)
        total = base.with_entities(func.count(User.id)).scalar() or 0
        rows = (
            base.order_by(User.id.desc())
            .offset(page * self.PAGE_SIZE)
            .limit(self.PAGE_SIZE)
            .all()
        )
        return [self._to_item(db, u) for u in rows], int(total)

    def search(self, db: Session, query: str, limit: int = 15) -> list[StudentListItem]:
        q = (query or "").strip()
        if not q:
            return []
        digits = re.sub(r"\D", "", q)
        filters = []
        if digits and len(digits) >= 4:
            filters.append(User.phone.ilike(f"%{digits[-10:]}%"))
        if any(ch.isalpha() or ("\u0600" <= ch <= "\u06FF") for ch in q) or not digits:
            filters.append(User.full_name.ilike(f"%{q}%"))
        if not filters:
            return []
        rows = (
            db.query(User)
            .filter(User.role == UserRole.STUDENT)
            .filter(or_(*filters))
            .order_by(User.id.desc())
            .limit(limit)
            .all()
        )
        return [self._to_item(db, u) for u in rows]

    def get_user(self, db: Session, user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    def _to_item(self, db: Session, user: User) -> StudentListItem:
        has_tg = (
            db.query(TelegramAccount.id)
            .filter(TelegramAccount.user_id == user.id)
            .first()
            is not None
        )
        enroll_n = db.query(func.count(Enrollment.id)).filter(Enrollment.user_id == user.id).scalar() or 0
        lic_n = (
            db.query(func.count(License.id))
            .filter(License.user_id == user.id, License.status == "active")
            .scalar()
            or 0
        )
        return StudentListItem(
            user_id=user.id,
            full_name=user.full_name or "—",
            phone=user.phone,
            has_telegram=has_tg,
            is_active=bool(user.is_active),
            enroll_count=int(enroll_n),
            active_license_count=int(lic_n),
        )

    def format_list_line(self, item: StudentListItem) -> str:
        source = "📱 تلگرام" if item.has_telegram else "📥 اسپات/قدیم"
        active = "" if item.is_active else " 🚫"
        phone = item.phone or "بدون شماره"
        return f"{item.full_name}{active}\n{phone} · {source} · 📚{item.enroll_count} · 🔑{item.active_license_count}"

    def format_detail(self, db: Session, user: User) -> str:
        tg = db.query(TelegramAccount).filter(TelegramAccount.user_id == user.id).first()
        enrollments = (
            db.query(Enrollment, Course)
            .join(Course, Course.id == Enrollment.course_id)
            .filter(Enrollment.user_id == user.id)
            .all()
        )
        licenses = (
            db.query(License)
            .filter(License.user_id == user.id)
            .order_by(License.id.desc())
            .limit(12)
            .all()
        )

        lines = [
            f"👤 <b>{user.full_name}</b>",
            f"شناسه داخلی: <code>{user.id}</code>",
            f"📱 {user.phone or '—'}",
            f"وضعیت: {'✅ فعال' if user.is_active else '🚫 غیرفعال'}",
        ]
        if tg:
            lines.append(f"تلگرام: <code>{tg.telegram_id}</code>" + (f" @{tg.username}" if tg.username else ""))
            lines.append("منبع: ثبت‌نام در ربات")
        else:
            lines.append("تلگرام: وصل نشده")
            lines.append("منبع: import / SpotPlayer (legacy)")

        lines.append("")
        lines.append("<b>دوره‌ها</b>")
        if not enrollments:
            lines.append("— هیچ دوره‌ای ثبت نشده")
        else:
            for _en, course in enrollments:
                lines.append(f"• {course.title}")

        lines.append("")
        lines.append("<b>لایسنس‌ها</b>")
        if not licenses:
            lines.append("— لایسنسی ثبت نشده")
        else:
            for lic in licenses:
                product = db.query(Course).filter(Course.id == lic.product_id).first()
                title = product.title if product else f"#{lic.product_id}"
                flag = " 🧪" if (lic.error_message or "") == "TEST_LICENSE" else ""
                lines.append(f"• {title}: {lic.status}{flag}")
                if lic.status == "active" and lic.license_key:
                    key = lic.license_key
                    preview = key if len(key) <= 28 else f"{key[:12]}…{key[-8:]}"
                    lines.append(f"  <code>{preview}</code>")

        return "\n".join(lines)

    def set_active(self, db: Session, user_id: int, active: bool) -> User | None:
        user = self.get_user(db, user_id)
        if not user or user.role != UserRole.STUDENT:
            return None
        user.is_active = active
        db.commit()
        db.refresh(user)
        return user
