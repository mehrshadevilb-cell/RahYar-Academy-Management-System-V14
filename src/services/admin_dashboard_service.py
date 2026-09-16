"""Owner-facing one-screen operational summary."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.config.settings import get_settings
from src.database.models.payment import Payment
from src.database.models.reservation import Reservation, ReservationStatus
from src.database.models.support_request import SupportRequest, SupportStatus
from src.database.models.user import User
from src.services.stats_service import StatsService


class AdminDashboardService:
    def __init__(self) -> None:
        self.stats = StatsService()
        self.settings = get_settings()

    def summary(self, db: Session) -> dict:
        base = self.stats.get_summary(db)
        open_support = (
            db.query(func.count(SupportRequest.id))
            .filter(SupportRequest.status == SupportStatus.OPEN)
            .scalar()
            or 0
        )
        pending_reservations = (
            db.query(func.count(Reservation.id))
            .filter(Reservation.status == ReservationStatus.PENDING)
            .scalar()
            or 0
        )
        active_users = (
            db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
        )
        ai_model = (self.settings.AI_DEFAULT_MODEL or "—").strip() or "—"
        return {
            **base,
            "open_support": open_support,
            "pending_reservations": pending_reservations,
            "active_users": active_users,
            "ai_default_model": ai_model,
            "chat_assistant": bool(self.settings.CHAT_ASSISTANT_ENABLED),
        }

    def format_fa(self, data: dict) -> str:
        return (
            "📊 <b>داشبورد مدیریت</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👥 کاربران فعال: <b>{data.get('active_users', 0)}</b>\n"
            f"💳 پرداخت در انتظار: <b>{data.get('pending_count', 0)}</b>\n"
            f"📅 رزرو در انتظار: <b>{data.get('pending_reservations', 0)}</b>\n"
            f"🆘 پشتیبانی باز: <b>{data.get('open_support', 0)}</b>\n"
            f"✅ پرداخت تأییدشده: <b>{data.get('approved_count', 0)}</b>\n"
            f"💰 درآمد تأییدشده: <b>{int(data.get('total_revenue') or 0):,}</b> تومان\n"
            f"🤖 دستیار: {'فعال' if data.get('chat_assistant') else 'خاموش'}\n"
            f"🧠 مدل پیش‌فرض AI: <code>{data.get('ai_default_model', '—')}</code>"
        )
