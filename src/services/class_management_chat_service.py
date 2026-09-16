"""Parse and execute admin class-management chat commands in Persian."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy.orm import Session

from src.database.models.attendance import AttendanceStatus
from src.database.models.online_enrollment import EnrollmentStatus, OnlineEnrollment
from src.database.models.user import User, UserRole
from src.services.attendance_service import AttendanceService
from src.services.online_enrollment_chat_parser import (
    parse_enrollment_chat,
    normalize_phone,
)
from src.services.online_enrollment_chat_service import OnlineEnrollmentChatService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.profile_service import ProfileService


class ClassChatIntent(str, Enum):
    ENROLL = "enroll"
    ABSENT = "absent"
    PRESENT = "present"
    STATUS = "status"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ClassChatResult:
    ok: bool
    message: str
    intent: ClassChatIntent = ClassChatIntent.UNKNOWN
    needs_confirm: bool = False
    draft_payload: dict | None = None


class ClassManagementChatService:
    def __init__(self) -> None:
        self.attendance = AttendanceService()
        self.enrollments = OnlineEnrollmentService()
        self.profiles = ProfileService()
        self.enroll_chat = OnlineEnrollmentChatService()

    def detect_intent(self, text: str) -> ClassChatIntent:
        t = (text or "").strip()
        low = t.casefold()
        if any(k in t for k in ("غیبت", "غایب", "نیومد", "نیامد", "absent")):
            return ClassChatIntent.ABSENT
        if any(k in t for k in ("حاضر", "حضور", "اومد", "آمد", "present")):
            return ClassChatIntent.PRESENT
        if any(k in t for k in ("چند جلسه", "وضعیت", "مانده", "باقی")) and not any(
            k in t for k in ("ثبت", "اضافه")
        ):
            return ClassChatIntent.STATUS
        if any(k in t for k in ("ثبت", "اضافه", "جلسه", "هفته", "کلاس")) and (
            normalize_phone(t) or "شماره" in t or re.search(r"09\d{9}", re.sub(r"\s", "", t))
        ):
            return ClassChatIntent.ENROLL
        if any(k in low for k in ("کمک", "help", "راهنما")):
            return ClassChatIntent.HELP
        if parse_enrollment_chat(t).ok:
            return ClassChatIntent.ENROLL
        return ClassChatIntent.UNKNOWN

    def help_text(self) -> str:
        return (
            "📚 <b>مدیریت کلاس با چت</b>\n\n"
            "مثال‌ها:\n"
            "• مهدی متاج 0937… هر سه‌شنبه ۴–۶ تنظیم/میکس ۲ جلسه مانده\n"
            "• علی امروز غیبت کرد\n"
            "• سارا امروز حاضر بود\n"
            "• وضعیت کلاس مهدی / چند جلسه مانده 0912…\n\n"
            "قانون غیبت: در هر ترم ۱۲ جلسه‌ای، <b>۱ غیبت اول رایگان</b>؛ "
            "از غیبت دوم به بعد از جلسات باقی‌مانده کم می‌شود.\n"
            "کنسلی طبق قوانین آکادمی جلسه مصرف نمی‌کند (دستور جدا)."
        )

    def _find_user(self, db: Session, text: str) -> User | None:
        phone = normalize_phone(text)
        if not phone:
            m = re.search(r"(?:\+?98|0)?9\d{9}", re.sub(r"[\s\-]", "", text))
            if m:
                phone = normalize_phone(m.group(0))
        if phone:
            user = self.profiles.get_profile_by_phone(db, phone)
            if user:
                return user
        # name search
        tokens = re.findall(r"[\u0600-\u06FFa-zA-Z]{2,}", text)
        stop = {
            "امروز", "دیروز", "غیبت", "غایب", "حاضر", "حضور", "کرد", "بود",
            "کلاس", "جلسه", "وضعیت", "مانده", "چند", "شماره", "با",
        }
        name_parts = [t for t in tokens if t not in stop]
        if not name_parts:
            return None
        query = " ".join(name_parts[:3])
        rows = (
            db.query(User)
            .filter(User.role == UserRole.STUDENT, User.full_name.ilike(f"%{query}%"))
            .limit(5)
            .all()
        )
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            return rows[0]  # best-effort; preview should show name
        return None

    def _active_enrollment(self, db: Session, user_id: int) -> OnlineEnrollment | None:
        rows = self.enrollments.get_active_by_user(db, user_id) or []
        active = [e for e in rows if e.status == EnrollmentStatus.ACTIVE]
        if not active:
            return None
        # Prefer enrollment with remaining sessions
        active.sort(key=lambda e: e.remaining_sessions, reverse=True)
        return active[0]

    def handle(self, db: Session, text: str) -> ClassChatResult:
        intent = self.detect_intent(text)
        if intent == ClassChatIntent.HELP or intent == ClassChatIntent.UNKNOWN:
            return ClassChatResult(True, self.help_text(), ClassChatIntent.HELP)

        if intent == ClassChatIntent.ENROLL:
            draft = parse_enrollment_chat(text)
            course = self.enroll_chat.match_course(db, draft.course_hint)
            user = None
            if draft.phone:
                user = self.profiles.get_profile_by_phone(db, draft.phone)
            preview = self.enroll_chat.format_preview(draft, course, user)
            payload = {
                "kind": "enroll",
                "name": draft.student_name,
                "phone": draft.phone,
                "course_hint": draft.course_hint,
                "sessions": draft.remaining_sessions,
                "weeks": draft.weeks,
                "plan": draft.plan,
                "weekday": draft.weekday,
                "t_from": draft.time_from,
                "t_to": draft.time_to,
                "raw": draft.raw_text,
            }
            return ClassChatResult(
                True,
                preview,
                ClassChatIntent.ENROLL,
                needs_confirm=True,
                draft_payload=payload,
            )

        user = self._find_user(db, text)
        if not user:
            return ClassChatResult(
                False,
                "هنرجو پیدا نشد. نام دقیق‌تر یا شماره موبایل را در متن بگذارید.",
                intent,
            )

        enrollment = self._active_enrollment(db, user.id)
        if not enrollment:
            return ClassChatResult(
                False,
                f"برای «{user.full_name}» ثبت‌نام فعال کلاس آنلاین پیدا نشد.",
                intent,
            )

        course_name = enrollment.online_course.name if enrollment.online_course else "کلاس"

        if intent == ClassChatIntent.STATUS:
            abs_n = self.attendance.count_absences_in_current_term(db, enrollment)
            return ClassChatResult(
                True,
                f"👤 {user.full_name}\n🎼 {course_name}\n"
                f"🎫 باقی‌مانده: {enrollment.remaining_sessions}\n"
                f"✅ برگزار شده: {enrollment.completed_sessions}\n"
                f"📝 غیبت در ترم جاری: {abs_n}",
                ClassChatIntent.STATUS,
            )

        if intent == ClassChatIntent.ABSENT:
            result = self.attendance.record(
                db,
                enrollment,
                AttendanceStatus.ABSENT,
                session_date=date.today().isoformat(),
                admin_note="ثبت از چت ادمین",
            )
            return ClassChatResult(
                result.ok,
                f"👤 {user.full_name} · {course_name}\n{result.message}",
                ClassChatIntent.ABSENT,
            )

        if intent == ClassChatIntent.PRESENT:
            result = self.attendance.record(
                db,
                enrollment,
                AttendanceStatus.PRESENT,
                session_date=date.today().isoformat(),
                admin_note="ثبت از چت ادمین",
            )
            return ClassChatResult(
                result.ok,
                f"👤 {user.full_name} · {course_name}\n{result.message}",
                ClassChatIntent.PRESENT,
            )

        return ClassChatResult(False, self.help_text(), ClassChatIntent.UNKNOWN)
