from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance, AttendanceStatus
from src.database.models.reservation import ReservationStatus
from src.database.models.online_enrollment import PaymentModel, EnrollmentStatus
from src.database.repositories.attendance_repository import AttendanceRepository
from src.services.installment_service import InstallmentService
from src.services.online_enrollment_service import OnlineEnrollmentService


class AttendanceService:
    """Records a reservation outcome exactly once.

    Only PRESENT consumes a session. ABSENT and CANCELLED never consume one.
    Re-clicking an attendance button is idempotent and cannot consume a second session.

    When remaining_sessions hits 0:
    - MONTHLY → PAUSED + next installment (pay for next 4 sessions)
    - TERM → if more cycles remain: PAUSED + next installment;
             otherwise ENDED (full term completed).
    """

    def __init__(self):
        self.repository = AttendanceRepository()
        self.installment_service = InstallmentService()
        self.enrollment_service = OnlineEnrollmentService()

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

        if status == AttendanceStatus.PRESENT:
            enrollment.completed_sessions += 1
            if enrollment.remaining_sessions > 0:
                enrollment.remaining_sessions -= 1

            if enrollment.remaining_sessions <= 0:
                if self.enrollment_service.should_create_next_cycle(enrollment):
                    enrollment.status = EnrollmentStatus.PAUSED
                    cycle_exhausted = True
                    self.installment_service.create_next_installment(db, enrollment)
                else:
                    enrollment.status = EnrollmentStatus.ENDED

            db.commit()
        else:
            db.commit()

        enrollment._cycle_exhausted = cycle_exhausted  # type: ignore[attr-defined]

        return attendance
