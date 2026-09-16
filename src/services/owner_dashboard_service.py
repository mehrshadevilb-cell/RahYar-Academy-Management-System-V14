"""Owner-facing daily operations and finance snapshot.

Keeps SQL/aggregation out of Telegram handlers. All amounts are integers
(toman). Dates for class reservations are stored as Jalali strings
(YYYY-MM-DD) matching the rest of the online-class stack.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from src.core.utils.jalali import format_jalali_date, gregorian_to_jalali
from src.database.models.installment import Installment, InstallmentStatus
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import EnrollmentStatus, OnlineEnrollment
from src.database.models.payment import Payment
from src.database.models.reservation import Reservation, ReservationStatus
from src.database.models.user import User

TEHRAN = ZoneInfo("Asia/Tehran")
DEFAULT_INACTIVE_DAYS = 14


def _jalali_today(now: datetime | None = None) -> str:
    d = (now or datetime.now(TEHRAN)).date()
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return format_jalali_date(jy, jm, jd)


def _day_bounds_utc_naive(day: date) -> tuple[datetime, datetime]:
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
    inactive_online_enrollments: int
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
            f"• ثبت‌نام فعال: {self.active_online_enrollments}\n"
            f"• بدون رزرو اخیر (۱۴ روز): {self.inactive_online_enrollments}\n\n"
            f"💰 اقساط\n"
            f"• سررسید امروز: {self.installments_due_today}\n"
            f"• معوق: {self.installments_overdue}\n\n"
            f"💵 درآمد تأییدشده (محصول)\n"
            f"• امروز: {self.revenue_today:,} تومان\n"
            f"• ۷ روز اخیر: {self.revenue_week:,} تومان\n"
            f"• ۳۰ روز اخیر: {self.revenue_month:,} تومان\n\n"
            f"👥 کل هنرجویان: {self.total_students}"
        )


@dataclass(frozen=True)
class InactiveEnrollmentRow:
    enrollment_id: int
    student_name: str
    course_name: str
    remaining_sessions: int
    days_since_activity: int | None


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

        inactive_rows = self.list_inactive_enrollments(db, days=DEFAULT_INACTIVE_DAYS, limit=500, now=now)
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
            inactive_online_enrollments=len(inactive_rows),
            total_students=int(total_students),
        )

    def list_inactive_enrollments(
        self,
        db: Session,
        *,
        days: int = DEFAULT_INACTIVE_DAYS,
        limit: int = 30,
        now: datetime | None = None,
    ) -> list[InactiveEnrollmentRow]:
        """Active enrollments with remaining sessions and no recent reservation."""
        now = now or datetime.now(TEHRAN)
        cutoff = (now - timedelta(days=days)).replace(tzinfo=None)

        last_activity = (
            db.query(
                Reservation.enrollment_id.label("enrollment_id"),
                func.max(Reservation.created_at).label("last_at"),
            )
            .group_by(Reservation.enrollment_id)
            .subquery()
        )

        rows = (
            db.query(OnlineEnrollment, User, OnlineCourse, last_activity.c.last_at)
            .join(User, User.id == OnlineEnrollment.user_id)
            .join(OnlineCourse, OnlineCourse.id == OnlineEnrollment.online_course_id)
            .outerjoin(last_activity, last_activity.c.enrollment_id == OnlineEnrollment.id)
            .filter(
                OnlineEnrollment.status == EnrollmentStatus.ACTIVE,
                OnlineEnrollment.remaining_sessions > 0,
                or_(
                    last_activity.c.last_at.is_(None),
                    last_activity.c.last_at < cutoff,
                ),
            )
            .order_by(last_activity.c.last_at.asc().nullsfirst(), OnlineEnrollment.id.asc())
            .limit(limit)
            .all()
        )

        result: list[InactiveEnrollmentRow] = []
        for enrollment, user, course, last_at in rows:
            days_since = None
            if last_at is not None:
                days_since = max(0, (now.replace(tzinfo=None) - last_at).days)
            result.append(
                InactiveEnrollmentRow(
                    enrollment_id=enrollment.id,
                    student_name=user.full_name if user else f"#{enrollment.user_id}",
                    course_name=course.name if course else "—",
                    remaining_sessions=int(enrollment.remaining_sessions or 0),
                    days_since_activity=days_since,
                )
            )
        return result

    def format_inactive_list(
        self,
        rows: list[InactiveEnrollmentRow],
        *,
        days: int = DEFAULT_INACTIVE_DAYS,
    ) -> str:
        if not rows:
            return (
                f"✅ هنرجوی فعالی بدون رزرو در {days} روز اخیر پیدا نشد.\n"
                "(فقط ثبت‌نام‌های فعال با جلسه باقی‌مانده بررسی می‌شوند.)"
            )
        lines = [
            f"😴 هنرجویان بدون رزرو اخیر ({days} روز)\n",
            f"تعداد نمایش: {len(rows)}\n",
        ]
        for row in rows:
            if row.days_since_activity is None:
                activity = "هرگز رزرو نکرده"
            else:
                activity = f"{row.days_since_activity} روز از آخرین رزرو"
            lines.append(
                f"• {row.student_name} | {row.course_name}\n"
                f"  جلسات باقی‌مانده: {row.remaining_sessions} | {activity}"
            )
        return "\n".join(lines)[:3500]

    @staticmethod
    def _approved_revenue(db: Session, start: datetime, end: datetime) -> int:
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
