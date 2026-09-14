from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance, AttendanceStatus
from src.database.models.online_enrollment import EnrollmentStatus, PaymentModel
from src.database.models.reservation import ReservationStatus
from src.database.repositories.attendance_repository import AttendanceRepository
from src.services.installment_service import InstallmentService


class AttendanceService:
    """Records a reservation outcome exactly once.

    Only PRESENT consumes a session. ABSENT and CANCELLED never consume one.
    When WEEKLY/MONTHLY remaining sessions hit 0, enrollment is PAUSED and
    the next payment cycle installment is created.
    """

    def __init__(self):
        self.repository = AttendanceRepository()
        self.installment_service = InstallmentService()

    def mark_attendance(
        self,
        db: Session,
        enrollment,
        session_date,
        status: AttendanceStatus,
        reservation_id: int | None = None,
        admin_note: str | None = None,
    ) -> Attendance:

        if reservation_id is not None:
            existing = self.repository.get_by_reservation_id(db, reservation_id)
            if existing:
                return existing

            from src.database.repositories.reservation_repository import (
                ReservationRepository,
            )

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

        if status == AttendanceStatus.PRESENT:
            enrollment.completed_sessions += 1
            if enrollment.remaining_sessions > 0:
                enrollment.remaining_sessions -= 1

            if enrollment.remaining_sessions <= 0:
                if enrollment.payment_model in (
                    PaymentModel.MONTHLY,
                    PaymentModel.WEEKLY,
                ):
                    enrollment.status = EnrollmentStatus.PAUSED
                    self.installment_service.create_next_installment(db, enrollment)
                else:
                    enrollment.status = EnrollmentStatus.ENDED

            db.commit()
        else:
            db.commit()

        return attendance
