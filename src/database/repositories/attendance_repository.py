from sqlalchemy.orm import Session

from src.database.models.attendance import Attendance


class AttendanceRepository:

    def create(self, db: Session, attendance: Attendance):
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        return attendance

    def get_by_reservation_id(self, db: Session, reservation_id: int):
        return (
            db.query(Attendance)
            .filter(Attendance.reservation_id == reservation_id)
            .first()
        )

    def count_present_since_last_installment(
        self, db: Session, enrollment_id: int, since_count: int
    ) -> int:
        """Total PRESENT attendances recorded for this enrollment so far."""
        from src.database.models.attendance import AttendanceStatus

        return (
            db.query(Attendance)
            .filter(
                Attendance.enrollment_id == enrollment_id,
                Attendance.status == AttendanceStatus.PRESENT,
            )
            .count()
        )
