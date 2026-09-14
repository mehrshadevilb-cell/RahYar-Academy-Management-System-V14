from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance, AttendanceStatus
from src.database.models.reservation import ReservationStatus
from src.database.models.online_enrollment import PaymentModel, EnrollmentStatus
from src.database.repositories.attendance_repository import AttendanceRepository
from src.services.installment_service import InstallmentService


class AttendanceService:
    """Records a reservation outcome exactly once.

    Only PRESENT consumes a session. ABSENT and CANCELLED never consume one.
    Re-clicking an attendance button is idempotent and cannot consume a second session.

    When remaining_sessions hits 0 on a WEEKLY/MONTHLY plan, enrollment is set to
    PAUSED (not ENDED) and a next installment is created so the student can pay
    for the following cycle.
    """

    def __init__(self):
        self.repository = AttendanceRepository()
        self.installment_service = InstallmentService()

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
                if enrollment.payment_model in (PaymentModel.WEEKLY, PaymentModel.MONTHLY):
                    enrollment.status = EnrollmentStatus.PAUSED
                    cycle_exhausted = True
                    self.installment_service.create_next_installment(db, enrollment)
                else:
                    enrollment.status = EnrollmentStatus.ENDED

            db.commit()
        else:
            db.commit()

        # Stash flag on the enrollment object for the handler to notify student.
        enrollment._cycle_exhausted = cycle_exhausted  # type: ignore[attr-defined]

        return attendance
