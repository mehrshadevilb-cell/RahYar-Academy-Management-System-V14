"""Owner-facing daily operations and finance snapshot.

Keeps SQL/aggregation out of Telegram handlers. All amounts are integers
(toman). Dates for class reservations are stored as Jalali strings
(YYYY-MM-DD) matching the rest of the online-class stack.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.utils.jalali import format_jalali_date, gregorian_to_jalali
from src.database.models.installment import Installment, InstallmentStatus
from src.database.models.online_enrollment import EnrollmentStatus, OnlineEnrollment
from src.database.models.payment import Payment
from src.database.models.reservation import Reservation, ReservationStatus
from src.database.models.user import User

TEHRAN = ZoneInfo("Asia/Tehran")


def _jalali_today(now: datetime | None = None) -> str:
    d = (now or datetime.now(TEHRAN)).date()
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return format_jalali_date(jy, jm, jd)


def _day_bounds_utc_naive(day: date) -> tuple[datetime, datetime]:
    """Payment timestamps are stored as naive UTC-ish datetimes via utcnow.

    For owner "today in Tehran" we convert Tehran calendar day to a UTC-naive
    window approximately spanning that civil day. Good enough for dashboard
    totals; exact bank reconciliation still uses CSV exports.
    """
    start_local = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=TEHRAN)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return start_utc, end_utc


@dataclass(frozen=True)
class OwnerDashboardSummary:
    jalali_today: str
    pending_payments: int
    pending_reservations: int
    classes_today: int
    installments_due_today: int
    installments_overdue: int
    revenue_today: int
    revenue_week: int
    revenue_month: int
    active_online_enrollments: int
    total_students: int

    def format_persian(self) -> str:
        return (
            f"📊 گزارش امروز\n"
            f"📅 {self.jalali_today}\n\n"
            f"⏳ در انتظار بررسی\n"
            f"• پرداخت محصول: {self.pending_payments}\n"
            f"• رزرو کلاس: {self.pending_reservations}\n\n"
            f"🎼 کلاس آنلاین\n"
            f"• کلاس‌های تأییدشدهٔ امروز: {self.classes_today}\n"
            f"• ثبت‌نام فعال: {self.active_online_enrollments}\n\n"
            f"💰 اقساط\n"
            f"• سررسید امروز: {self.installments_due_today}\n"
            f"• معوق: {self.installments_overdue}\n\n"
            f"💵 درآمد تأییدشده (محصول)\n"
            f"• امروز: {self.revenue_today:,} تومان\n"
            f"• ۷ روز اخیر: {self.revenue_week:,} تومان\n"
            f"• ۳۰ روز اخیر: {self.revenue_month:,} تومان\n\n"
            f"👥 کل هنرجویان: {self.total_students}"
        )


class OwnerDashboardService:
    """Aggregate numbers the academy owner needs every morning."""

    def get_summary(self, db: Session, *, now: datetime | None = None) -> OwnerDashboardSummary:
        now = now or datetime.now(TEHRAN)
        today_local = now.date()
        jalali_today = _jalali_today(now)

        pending_payments = (
            db.query(func.count(Payment.id))
            .filter(Payment.status == "pending")
            .scalar()
            or 0
        )

        pending_reservations = (
            db.query(func.count(Reservation.id))
            .filter(
                Reservation.status.in_(
                    (
                        ReservationStatus.PENDING,
                        ReservationStatus.PAYMENT_SUBMITTED,
                    )
                )
            )
            .scalar()
            or 0
        )

        classes_today = (
            db.query(func.count(Reservation.id))
            .filter(
                Reservation.status == ReservationStatus.CONFIRMED,
                Reservation.requested_date == jalali_today,
            )
            .scalar()
            or 0
        )

        installments_due_today = (
            db.query(func.count(Installment.id))
            .filter(
                Installment.status == InstallmentStatus.PENDING,
                Installment.due_date == today_local,
            )
            .scalar()
            or 0
        )

        installments_overdue = (
            db.query(func.count(Installment.id))
            .filter(Installment.status == InstallmentStatus.OVERDUE)
            .scalar()
            or 0
        )

        start_today, end_today = _day_bounds_utc_naive(today_local)
        start_week, _ = _day_bounds_utc_naive(today_local - timedelta(days=6))
        start_month, _ = _day_bounds_utc_naive(today_local - timedelta(days=29))

        revenue_today = self._approved_revenue(db, start_today, end_today)
        revenue_week = self._approved_revenue(db, start_week, end_today)
        revenue_month = self._approved_revenue(db, start_month, end_today)

        active_online = (
            db.query(func.count(OnlineEnrollment.id))
            .filter(OnlineEnrollment.status == EnrollmentStatus.ACTIVE)
            .scalar()
            or 0
        )

        total_students = db.query(func.count(User.id)).scalar() or 0

        return OwnerDashboardSummary(
            jalali_today=jalali_today,
            pending_payments=int(pending_payments),
            pending_reservations=int(pending_reservations),
            classes_today=int(classes_today),
            installments_due_today=int(installments_due_today),
            installments_overdue=int(installments_overdue),
            revenue_today=int(revenue_today),
            revenue_week=int(revenue_week),
            revenue_month=int(revenue_month),
            active_online_enrollments=int(active_online),
            total_students=int(total_students),
        )

    @staticmethod
    def _approved_revenue(db: Session, start: datetime, end: datetime) -> int:
        """Sum approved product payments whose review (or create) time falls in range."""
        # Prefer reviewed_at when present; fall back to created_at for older rows.
        stamp = func.coalesce(Payment.reviewed_at, Payment.created_at)
        total = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(
                Payment.status == "approved",
                stamp >= start,
                stamp < end,
            )
            .scalar()
        )
        return int(total or 0)
