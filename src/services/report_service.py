import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from src.database.models.payment import Payment
from src.database.models.user import User, UserRole
from src.database.models.course import Course
from src.database.models.student_profile import StudentProfile
from src.database.models.telegram_account import TelegramAccount
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.online_course import OnlineCourse
from src.database.models.installment import Installment, InstallmentStatus


def _csv_bytes(header: list[str], rows: list[list]) -> bytes:
    """
    Renders rows to CSV bytes with a UTF-8 BOM, so the file opens with
    correct Persian text (not mojibake) when double-clicked straight into
    Excel - plain utf-8 without the BOM is what Excel gets wrong.
    """

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


class ReportService:
    """
    Owner-facing CSV exports. Each method returns raw CSV bytes ready to
    hand to `Bot.send_document` - no Telegram concerns live here, keeping
    this reusable if reports are ever needed outside the bot (e.g. a
    scheduled email export).
    """

    def payments_report(self, db: Session, status: str | None = None) -> bytes:

        query = db.query(Payment).order_by(Payment.created_at.desc())

        if status:
            query = query.filter(Payment.status == status)

        payments = query.all()

        user_ids = {p.user_id for p in payments}
        course_ids = {p.course_id for p in payments}

        users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
        courses = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()} if course_ids else {}

        rows = []
        for p in payments:
            user = users.get(p.user_id)
            course = courses.get(p.course_id)
            rows.append([
                p.id,
                user.full_name if user else "—",
                user.phone if user and user.phone else "—",
                course.title if course else "—",
                p.amount,
                p.discount_amount,
                p.status,
                p.transaction_id or "—",
                p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "—",
                p.reviewed_at.strftime("%Y-%m-%d %H:%M") if p.reviewed_at else "—",
            ])

        return _csv_bytes(
            ["شناسه", "نام هنرجو", "شماره تماس", "محصول", "مبلغ", "مبلغ تخفیف",
             "وضعیت", "کد پیگیری", "تاریخ ثبت", "تاریخ بررسی"],
            rows,
        )

    def students_report(self, db: Session) -> bytes:

        students = (
            db.query(User)
            .filter(User.role == UserRole.STUDENT)
            .order_by(User.created_at.desc())
            .all()
        )

        profiles = {
            sp.user_id: sp
            for sp in db.query(StudentProfile).all()
        }
        telegram_accounts = {
            ta.user_id: ta
            for ta in db.query(TelegramAccount).all()
        }

        rows = []
        for u in students:
            profile = profiles.get(u.id)
            account = telegram_accounts.get(u.id)
            rows.append([
                u.id,
                u.full_name,
                u.phone or "—",
                account.username if account and account.username else "—",
                profile.level if profile and profile.level else "—",
                "فعال" if u.is_active else "غیرفعال",
                u.created_at.strftime("%Y-%m-%d") if u.created_at else "—",
            ])

        return _csv_bytes(
            ["شناسه", "نام کامل", "شماره تماس", "یوزرنیم تلگرام", "سطح", "وضعیت", "تاریخ ثبت‌نام"],
            rows,
        )

    def online_enrollments_report(self, db: Session) -> bytes:

        enrollments = (
            db.query(OnlineEnrollment)
            .order_by(OnlineEnrollment.created_at.desc())
            .all()
        )

        user_ids = {e.user_id for e in enrollments}
        course_ids = {e.online_course_id for e in enrollments}

        users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
        courses = {
            c.id: c for c in db.query(OnlineCourse).filter(OnlineCourse.id.in_(course_ids)).all()
        } if course_ids else {}

        rows = []
        for e in enrollments:
            user = users.get(e.user_id)
            course = courses.get(e.online_course_id)
            rows.append([
                e.id,
                user.full_name if user else "—",
                course.name if course else "—",
                e.payment_model.value,
                e.remaining_sessions,
                e.completed_sessions,
                e.status.value,
                e.created_at.strftime("%Y-%m-%d") if e.created_at else "—",
            ])

        return _csv_bytes(
            ["شناسه", "هنرجو", "کلاس", "مدل پرداخت", "جلسات باقی‌مانده",
             "جلسات برگزارشده", "وضعیت", "تاریخ ثبت‌نام"],
            rows,
        )

    def installments_report(self, db: Session, status: InstallmentStatus | None = None) -> bytes:

        query = db.query(Installment).order_by(Installment.due_date.asc())

        if status:
            query = query.filter(Installment.status == status)

        installments = query.all()

        enrollment_ids = {i.enrollment_id for i in installments}
        enrollments = {
            e.id: e
            for e in db.query(OnlineEnrollment).filter(OnlineEnrollment.id.in_(enrollment_ids)).all()
        } if enrollment_ids else {}

        user_ids = {e.user_id for e in enrollments.values()}
        course_ids = {e.online_course_id for e in enrollments.values()}

        users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
        courses = {
            c.id: c for c in db.query(OnlineCourse).filter(OnlineCourse.id.in_(course_ids)).all()
        } if course_ids else {}

        rows = []
        for i in installments:
            enrollment = enrollments.get(i.enrollment_id)
            user = users.get(enrollment.user_id) if enrollment else None
            course = courses.get(enrollment.online_course_id) if enrollment else None
            rows.append([
                i.id,
                user.full_name if user else "—",
                course.name if course else "—",
                i.installment_number,
                i.amount,
                i.due_date.strftime("%Y-%m-%d") if i.due_date else "—",
                i.paid_date.strftime("%Y-%m-%d") if i.paid_date else "—",
                i.status.value,
            ])

        return _csv_bytes(
            ["شناسه", "هنرجو", "کلاس", "شماره قسط", "مبلغ", "سررسید", "تاریخ پرداخت", "وضعیت"],
            rows,
        )
