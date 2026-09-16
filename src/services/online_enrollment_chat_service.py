"""Apply chat-parsed online enrollment drafts with owner confirmation."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import PaymentModel
from src.database.models.user import User, UserRole
from src.services.online_course_service import OnlineCourseService
from src.services.online_enrollment_chat_parser import ChatEnrollmentDraft, normalize_phone
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.profile_service import ProfileService


@dataclass
class ApplyResult:
    ok: bool
    message: str
    enrollment_id: int | None = None


class OnlineEnrollmentChatService:
    def __init__(self) -> None:
        self.courses = OnlineCourseService()
        self.enrollments = OnlineEnrollmentService()
        self.profiles = ProfileService()

    def match_course(self, db: Session, hint: str | None) -> OnlineCourse | None:
        if not hint:
            return None
        all_courses = self.courses.get_all_courses(db) or []
        hint_l = hint.casefold()
        # Exact / substring on name
        for course in all_courses:
            name = (course.name or "").casefold()
            if hint_l in name or name in hint_l:
                return course
        # Keyword overlap
        for course in all_courses:
            name = course.name or ""
            for token in ("میکس", "مستر", "تنظیم", "پیانو", "تئوری", "هارمونی", "گوش"):
                if token in hint and token in name:
                    return course
        active = [c for c in all_courses if c.is_active]
        return active[0] if len(active) == 1 else None

    def get_or_create_student(self, db: Session, name: str | None, phone: str) -> User:
        phone_n = normalize_phone(phone) or phone
        user = self.profiles.get_profile_by_phone(db, phone_n)
        if user:
            if name and (not user.full_name or len(user.full_name) < 2):
                user.full_name = name[:100]
                db.commit()
                db.refresh(user)
            return user
        user = User(
            full_name=(name or "هنرجوی آنلاین")[:100],
            phone=phone_n,
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def format_preview(self, draft: ChatEnrollmentDraft, course: OnlineCourse | None, user: User | None) -> str:
        sessions = draft.remaining_sessions
        if sessions is None and draft.weeks:
            sessions = draft.weeks
        lines = [
            "📝 <b>پیش‌نمایش ثبت کلاس</b>",
            "━━━━━━━━━━━━━━━━━━",
            f"👤 نام: {draft.student_name or (user.full_name if user else '—')}",
            f"📱 شماره: {draft.phone or '—'}",
            f"🎼 کلاس: {(course.name if course else draft.course_hint) or '—'}",
            f"🎫 جلسات: {sessions if sessions is not None else '—'}",
            f"📦 پلن: {'ماهانه' if draft.plan == 'monthly' else 'ترمی'}",
        ]
        note = draft.schedule_note()
        if note:
            lines.append(f"📅 برنامه: {note}")
        if draft.warnings:
            lines.append("")
            lines.append("⚠️ " + " | ".join(draft.warnings))
        lines.append("")
        lines.append("اگر درست است «تأیید» را بزنید.")
        return "\n".join(lines)

    def apply(self, db: Session, draft: ChatEnrollmentDraft) -> ApplyResult:
        if not draft.phone:
            return ApplyResult(False, "شماره موبایل لازم است.")
        sessions = draft.remaining_sessions
        if sessions is None and draft.weeks:
            sessions = draft.weeks
        if sessions is None or sessions < 0:
            return ApplyResult(False, "تعداد جلسه مشخص نیست.")

        course = self.match_course(db, draft.course_hint)
        if not course:
            return ApplyResult(
                False,
                "کلاس آنلاین مطابق متن پیدا نشد. اول کلاس را در «مدیریت کلاس‌های آنلاین» بسازید "
                f"یا نام دقیق‌تری بفرستید. (راهنما: {draft.course_hint or '—'})",
            )

        user = self.get_or_create_student(db, draft.student_name, draft.phone)
        existing = self.enrollments.get_active_for_user_course(db, user.id, course.id)
        note_bits = [draft.schedule_note(), "ثبت از چت ادمین"]
        admin_notes = " | ".join(b for b in note_bits if b)[:500]

        if existing:
            enrollment = self.enrollments.set_remaining_sessions(db, existing, sessions)
            enrollment = self.enrollments.set_admin_notes(db, enrollment, admin_notes)
            return ApplyResult(
                True,
                f"✅ ثبت‌نام قبلی «{user.full_name}» در «{course.name}» به‌روز شد.\n"
                f"جلسات باقی‌مانده: {enrollment.remaining_sessions}\n📅 {admin_notes}",
                enrollment.id,
            )

        payment_model = PaymentModel.MONTHLY if draft.plan == "monthly" else PaymentModel.TERM
        enrollment = self.enrollments.create_enrollment(
            db,
            user_id=user.id,
            online_course=course,
            payment_model=payment_model,
            remaining_sessions=sessions,
            admin_notes=admin_notes,
        )
        return ApplyResult(
            True,
            f"✅ «{user.full_name}» در «{course.name}» ثبت شد.\n"
            f"جلسات: {enrollment.remaining_sessions}\n📅 {admin_notes}",
            enrollment.id,
        )
