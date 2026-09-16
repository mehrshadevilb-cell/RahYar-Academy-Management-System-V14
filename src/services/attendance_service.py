"""Record present/absent for online enrollments with academy absence rules.

Business rules:
- PRESENT: consumes one remaining session, increments completed_sessions.
- CANCELLED: never consumes a session.
- ABSENT: first absence in a term window is free; further absences deduct
  one remaining session each.

Term window size defaults to 12 sessions (configurable per call).
Absences are counted among the current term window based on ordered
attendance rows for the enrollment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance, AttendanceStatus
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.reservation import Reservation, ReservationStatus
from src.services.online_enrollment_service import OnlineEnrollmentService

DEFAULT_TERM_SIZE = 12
FREE_ABSENCES_PER_TERM = 1


@dataclass
class AttendanceResult:
    ok: bool
    message: str
    attendance_id: int | None = None
    deducted: bool = False
    absence_index_in_term: int | None = None
    remaining_sessions: int | None = None


class AttendanceService:
    def __init__(self) -> None:
        self.enrollments = OnlineEnrollmentService()

    def _list_absences(self, db: Session, enrollment_id: int) -> list[Attendance]:
        return (
            db.query(Attendance)
            .filter(
                Attendance.enrollment_id == enrollment_id,
                Attendance.status == AttendanceStatus.ABSENT,
            )
            .order_by(Attendance.id.asc())
            .all()
        )

    def count_absences_in_current_term(
        self,
        db: Session,
        enrollment: OnlineEnrollment,
        *,
        term_size: int = DEFAULT_TERM_SIZE,
    ) -> int:
        """How many absences fall in the current term bucket.

        Term bucket = floor(completed_sessions / term_size).
        We approximate by counting absences whose order index falls in the
        same bucket as the next session index (completed + absences so far).
        Simpler academy rule: count ALL absences on this enrollment and
        apply free quota of FREE_ABSENCES_PER_TERM per every term_size
        completed+absent slots — practically: free if total_absences < 1
        for first term; for multi-term use absences % related to term.

        Implemented rule matching owner request:
        «اولین غیبت در هر ترم ۱۲ جلسه‌ای آزاد؛ بیش از ۱ بار از جلسات کم شود»
        → within each block of term_size attendance-events (present+absent),
        only the first ABSENT is free.
        """
        rows = (
            db.query(Attendance)
            .filter(
                Attendance.enrollment_id == enrollment.id,
                Attendance.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.ABSENT]),
            )
            .order_by(Attendance.id.asc())
            .all()
        )
        # Current open term = last incomplete chunk of term_size events
        start = ((len(rows) - 1) // term_size) * term_size if rows else 0
        chunk = rows[start:]
        return sum(1 for r in chunk if r.status == AttendanceStatus.ABSENT)

    def record(
        self,
        db: Session,
        enrollment: OnlineEnrollment,
        status: AttendanceStatus,
        *,
        session_date: str | None = None,
        admin_note: str | None = None,
        term_size: int = DEFAULT_TERM_SIZE,
        free_absences: int = FREE_ABSENCES_PER_TERM,
    ) -> AttendanceResult:
        if status == AttendanceStatus.CANCELLED:
            row = Attendance(
                enrollment_id=enrollment.id,
                session_date=session_date or date.today().isoformat(),
                status=status,
                admin_note=(admin_note or "")[:500] or None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return AttendanceResult(
                True,
                "ثبت شد: کنسلی (جلسه مصرف نشد).",
                row.id,
                False,
                remaining_sessions=enrollment.remaining_sessions,
            )

        if status == AttendanceStatus.PRESENT:
            row = Attendance(
                enrollment_id=enrollment.id,
                session_date=session_date or date.today().isoformat(),
                status=status,
                admin_note=(admin_note or "")[:500] or None,
            )
            db.add(row)
            enrollment.remaining_sessions = max(0, int(enrollment.remaining_sessions) - 1)
            enrollment.completed_sessions = int(enrollment.completed_sessions or 0) + 1
            if enrollment.remaining_sessions == 0:
                from src.database.models.online_enrollment import EnrollmentStatus
                enrollment.status = EnrollmentStatus.ENDED
            db.commit()
            db.refresh(row)
            db.refresh(enrollment)
            return AttendanceResult(
                True,
                f"✅ حضور ثبت شد. جلسات باقی‌مانده: {enrollment.remaining_sessions}",
                row.id,
                True,
                remaining_sessions=enrollment.remaining_sessions,
            )

        # ABSENT
        absences_in_term = self.count_absences_in_current_term(
            db, enrollment, term_size=term_size
        )
        next_index = absences_in_term + 1
        deduct = next_index > free_absences

        row = Attendance(
            enrollment_id=enrollment.id,
            session_date=session_date or date.today().isoformat(),
            status=AttendanceStatus.ABSENT,
            admin_note=(admin_note or "")[:500] or None,
        )
        db.add(row)

        if deduct:
            enrollment.remaining_sessions = max(0, int(enrollment.remaining_sessions) - 1)
            enrollment.completed_sessions = int(enrollment.completed_sessions or 0) + 1
            note_suffix = f"غیبت شماره {next_index} در ترم — جلسه کسر شد"
        else:
            note_suffix = f"غیبت شماره {next_index} در ترم — رایگان (بدون کسر)"

        if row.admin_note:
            row.admin_note = f"{row.admin_note} | {note_suffix}"[:500]
        else:
            row.admin_note = note_suffix

        db.commit()
        db.refresh(row)
        db.refresh(enrollment)

        if deduct:
            msg = (
                f"⚠️ غیبت ثبت شد (بار {next_index} در این ترم {term_size} جلسه‌ای).\n"
                f"چون بیش از {free_absences} غیبت رایگان بود، یک جلسه کم شد.\n"
                f"جلسات باقی‌مانده: {enrollment.remaining_sessions}"
            )
        else:
            msg = (
                f"📝 غیبت ثبت شد (بار {next_index} در این ترم).\n"
                f"اولین غیبت‌ها تا سقف {free_absences} رایگان است؛ جلسه‌ای کم نشد.\n"
                f"جلسات باقی‌مانده: {enrollment.remaining_sessions}"
            )

        return AttendanceResult(
            True,
            msg,
            row.id,
            deduct,
            next_index,
            enrollment.remaining_sessions,
        )

    def mark_attendance(
        self,
        db: Session,
        enrollment: OnlineEnrollment,
        session_date: str,
        status: AttendanceStatus,
        reservation_id: int | None = None,
    ) -> AttendanceResult:
        """Backward-compatible reservation-facing attendance entry point.

        Older admin handlers call this method directly. Repeated callbacks for
        the same reservation must not consume another session.
        """
        if reservation_id is not None:
            existing = (
                db.query(Attendance)
                .filter(Attendance.reservation_id == reservation_id)
                .first()
            )
            if existing:
                return AttendanceResult(
                    True,
                    "حضور این جلسه قبلاً ثبت شده است.",
                    existing.id,
                    False,
                    remaining_sessions=enrollment.remaining_sessions,
                )

        result = self.record(
            db,
            enrollment,
            status,
            session_date=session_date,
        )
        if result.attendance_id and reservation_id is not None:
            row = db.query(Attendance).filter(Attendance.id == result.attendance_id).first()
            if row:
                row.reservation_id = reservation_id
                reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
                if reservation and status == AttendanceStatus.PRESENT:
                    reservation.status = ReservationStatus.COMPLETED
                elif reservation and status == AttendanceStatus.CANCELLED:
                    reservation.status = ReservationStatus.CANCELLED
                db.commit()
        return result
