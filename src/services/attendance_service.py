from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance, AttendanceStatus
from src.database.models.reservation import ReservationStatus
from src.database.models.online_enrollment import PaymentModel, EnrollmentStatus
from src.database.repositories.attendance_repository import AttendanceRepository
from src.services.installment_service import InstallmentService


SESSIONS_PER_INSTALLMENT_CYCLE = 4


class AttendanceService:
    """Records a reservation outcome exactly once.

    PRESENT consumes a session. The first ABSENT is a free extension; later
    absences consume the reserved session. CANCELLED never consumes one.
    Re-clicking an attendance button is idempotent and cannot consume a second session.
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

        if status == AttendanceStatus.PRESENT:
            enrollment.completed_sessions += 1
            if enrollment.remaining_sessions > 0:
                enrollment.remaining_sessions -= 1
            if enrollment.remaining_sessions <= 0:
                enrollment.status = EnrollmentStatus.ENDED

            db.commit()

            if (
                enrollment.payment_model == PaymentModel.MONTHLY
                and enrollment.completed_sessions % SESSIONS_PER_INSTALLMENT_CYCLE == 0
                and enrollment.status != EnrollmentStatus.ENDED
            ):
                self.installment_service.create_next_installment(db, enrollment)

        elif status == AttendanceStatus.ABSENT:
            previous_absences = (
                db.query(Attendance)
                .filter(
                    Attendance.enrollment_id == enrollment.id,
                    Attendance.status == AttendanceStatus.ABSENT,
                )
                .count()
            ) - 1  # the current absence was inserted immediately above
            if previous_absences >= 1:
                enrollment.completed_sessions += 1
                if enrollment.remaining_sessions > 0:
                    enrollment.remaining_sessions -= 1
                if enrollment.remaining_sessions <= 0:
                    enrollment.status = EnrollmentStatus.ENDED
            elif reservation_id is not None:
                # Preserve the first missed lesson by adding one confirmed
                # lesson after the current reservation run (same weekly day).
                try:
                    current = date.fromisoformat(str(session_date))
                    replacement = current + timedelta(days=7)
                    from src.database.repositories.reservation_repository import ReservationRepository
                    repo = ReservationRepository()
                    existing_dates = repo.get_for_enrollment(db, enrollment.id)
                    while any(str(item.requested_date) == replacement.isoformat() for item in existing_dates):
                        replacement += timedelta(days=7)
                    from src.database.models.reservation import Reservation
                    db.add(Reservation(
                        enrollment_id=enrollment.id,
                        requested_date=replacement.isoformat(),
                        requested_time=reservation.requested_time,
                        status=ReservationStatus.CONFIRMED,
                        admin_notes="automatic extension for first absence",
                    ))
                except (TypeError, ValueError):
                    pass
            db.commit()
        else:
            db.commit()

        return attendance
