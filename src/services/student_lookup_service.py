"""Admin lookup of students by phone or name (read-only)."""
from __future__ import annotations

import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.database.models.enrollment import Enrollment
from src.database.models.license import License
from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


class StudentLookupService:
    def search(self, db: Session, query: str, limit: int = 15) -> list[User]:
        q = (query or "").strip()
        if not q:
            return []

        digits = _digits_only(q)
        filters = []
        if digits and len(digits) >= 4:
            # Match stored 09… forms and partial tails.
            filters.append(User.phone.ilike(f"%{digits[-10:]}%"))
            if digits.startswith("98") and len(digits) >= 12:
                filters.append(User.phone.ilike(f"%0{digits[2:]}%"))
        if not digits or any(ch.isalpha() or ("\u0600" <= ch <= "\u06FF") for ch in q):
            filters.append(User.full_name.ilike(f"%{q}%"))

        if not filters:
            return []

        return (
            db.query(User)
            .filter(or_(*filters))
            .order_by(User.id.desc())
            .limit(limit)
            .all()
        )

    def format_user_card(self, db: Session, user: User) -> str:
        tg = (
            db.query(TelegramAccount)
            .filter(TelegramAccount.user_id == user.id)
            .first()
        )
        enroll_n = db.query(Enrollment).filter(Enrollment.user_id == user.id).count()
        lic_active = (
            db.query(License)
            .filter(License.user_id == user.id, License.status == "active")
            .count()
        )
        lines = [
            f"👤 <b>{user.full_name}</b>",
            f"📱 {user.phone or '—'}",
            f"نقش: {user.role.value if hasattr(user.role, 'value') else user.role}",
            f"وضعیت: {'فعال' if user.is_active else 'غیرفعال'}",
            f"دوره‌ها: {enroll_n} | لایسنس فعال: {lic_active}",
        ]
        if tg:
            lines.append(f"Telegram: <code>{tg.telegram_id}</code>")
        else:
            lines.append("Telegram: هنوز وصل نشده (legacy / بدون /start)")
        return "\n".join(lines)
