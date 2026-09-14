from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance, AttendanceStatus
from src.database.models.reservation import ReservationStatus
from src.database.models.online_enrollment import (
    EnrollmentStatus,
    FREE_MISSES_PER_12_SESSIONS,
)
from src.database.repositories.attendance_repository import AttendanceRepository
from src.services.installment_service import InstallmentService
from src.services.online_enrollment_service import OnlineEnrollmentService


class AttendanceService:
    """Records a reservation outcome exactly once.

    Session consumption:
    - PRESENT → always consumes 1 remaining session.
    - ABSENT or CANCELLED → 1 free miss per 12 sessions (term block);
      further misses consume 1 remaining session each.

    When remaining_sessions hits 0 after a consuming event:
    - MONTHLY → PAUSED + next installment
    - TERM → next cycle if remaining, else ENDED
    """

    def __init__(self):
        self.repository = AttendanceRepository()
        self.installment_service = InstallmentService()
        self.enrollment_service = OnlineEnrollmentService()

    def _allowed_free_misses(self, enrollment) -> int:
        """1 free miss per every 12 completed+remaining capacity of the plan.

        For a standard term (12 sessions) this is 1 free miss for the whole term.
        For longer enrollments it scales: floor(term_sessions / 12) * FREE_MISSES.
        """
        course = enrollment.online_course
        term_size = getattr(course, "term_sessions", None) or 12
        blocks = max(1, term_size // 12)
        return blocks * FREE_MISSES_PER_12_SESSIONS

    def _consume_session(self, db: Session, enrollment) -> bool:
        """Decrement remaining_sessions; return True if cycle is now exhausted."""
        enrollment.completed_sessions += 1
        if enrollment.remaining_sessions > 0:
            enrollment.remaining_sessions -= 1

        if enrollment.remaining_sessions <= 0:
            if self.enrollment_service.should_create_next_cycle(enrollment):
                enrollment.status = EnrollmentStatus.PAUSED
                self.installment_service.create_next_installment(db, enrollment)
                return True
            enrollment.status = EnrollmentStatus.ENDED
        return False

    def _handle_miss(self, db: Session, enrollment) -> tuple[bool, str]:
        """Apply free-miss or charged-miss rules.

        Returns (cycle_exhausted, outcome) where outcome is
        'free_miss' or 'charged_miss'.
        """
        used = enrollment.free_cancels_used or 0
        allowed = self._allowed_free_misses(enrollment)

        if used < allowed:
            enrollment.free_cancels_used = used + 1
            return False, "free_miss"

        cycle_exhausted = self._consume_session(db, enrollment)
        return cycle_exhausted, "charged_miss"

    def mark_attendance(
        self, db: Session, enrollment, session_date, status: AttendanceStatus,
        reservation_id: int | None = None, admin_note: str | None = None,
    ) -> Attendance:
        if reservation_id is not None:
            existing = self.repository.get_by_reservation_id(db, reservation_id)
            if existing:
                return existing

            from src.database.repositories.reservation_repository import ReservationRepository
            reservation = ReservationRepository().get_by_id(db, reservation_id)
            if not reservation or reservation.status != ReservationStatus.CONFIRMED:
                raise ValueError("فقط رزرو تاییدشده می‌تواند حضور و غیاب شود.")

        attendance = self.repository.create(
            db,
            Attendance(
                enrollment_id=enrollment.id,
                reservation_id=reservation_id,
                session_date=session_date,
                status=status,
                admin_note=admin_note,
            ),
        )

        if reservation_id is not None:
            reservation.status = ReservationStatus.COMPLETED

        cycle_exhausted = False
        miss_outcome: str | None = None

        if status == AttendanceStatus.PRESENT:
            cycle_exhausted = self._consume_session(db, enrollment)
            db.commit()

        elif status in (AttendanceStatus.ABSENT, AttendanceStatus.CANCELLED):
            # Every absence/cancel beyond the 1 free miss per 12 sessions
            # consumes a paid session.
            cycle_exhausted, miss_outcome = self._handle_miss(db, enrollment)
            db.commit()

        else:
            db.commit()

        enrollment._cycle_exhausted = cycle_exhausted  # type: ignore[attr-defined]
        enrollment._miss_outcome = miss_outcome  # type: ignore[attr-defined]
        # Back-compat alias for older handler code
        enrollment._cancel_outcome = (  # type: ignore[attr-defined]
            "free_cancel" if miss_outcome == "free_miss"
            else "charged_cancel" if miss_outcome == "charged_miss"
            else None
        )

        return attendance
