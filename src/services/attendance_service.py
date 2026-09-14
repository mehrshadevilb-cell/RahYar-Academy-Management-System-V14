from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance, AttendanceStatus
from src.database.models.reservation import ReservationStatus
from src.database.models.online_enrollment import (
    EnrollmentStatus,
    FREE_CANCELS_PER_TERM,
)
from src.database.repositories.attendance_repository import AttendanceRepository
from src.services.installment_service import InstallmentService
from src.services.online_enrollment_service import OnlineEnrollmentService


class AttendanceService:
    """Records a reservation outcome exactly once.

    Session consumption:
    - PRESENT → always consumes 1 remaining session.
    - ABSENT → does not consume.
    - CANCELLED → first free cancel per term does not consume;
      further cancels consume 1 session (count as charged absence).

    When remaining_sessions hits 0 after a consuming event:
    - MONTHLY → PAUSED + next installment
    - TERM → next cycle if remaining, else ENDED
    """

    def __init__(self):
        self.repository = AttendanceRepository()
        self.installment_service = InstallmentService()
        self.enrollment_service = OnlineEnrollmentService()

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
        # free_cancel | charged_cancel | None
        cancel_outcome: str | None = None

        if status == AttendanceStatus.PRESENT:
            cycle_exhausted = self._consume_session(db, enrollment)
            db.commit()

        elif status == AttendanceStatus.CANCELLED:
            used = enrollment.free_cancels_used or 0
            if used < FREE_CANCELS_PER_TERM:
                enrollment.free_cancels_used = used + 1
                cancel_outcome = "free_cancel"
                db.commit()
            else:
                # Extra cancel beyond the free allowance → counts as session used.
                cycle_exhausted = self._consume_session(db, enrollment)
                cancel_outcome = "charged_cancel"
                db.commit()

        else:
            # ABSENT: no session consumption
            db.commit()

        enrollment._cycle_exhausted = cycle_exhausted  # type: ignore[attr-defined]
        enrollment._cancel_outcome = cancel_outcome  # type: ignore[attr-defined]

        return attendance
