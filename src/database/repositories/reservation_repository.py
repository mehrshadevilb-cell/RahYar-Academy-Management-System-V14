from sqlalchemy.orm import Session

from src.database.models.reservation import Reservation, ReservationStatus


class ReservationRepository:
    def create(self, db: Session, reservation: Reservation):
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        return reservation

    def get_by_id(self, db: Session, reservation_id: int):
        return db.query(Reservation).filter(Reservation.id == reservation_id).first()

    def get_pending(self, db: Session):
        return (
            db.query(Reservation)
            .filter(Reservation.status == ReservationStatus.PENDING)
            .order_by(Reservation.requested_date, Reservation.requested_time)
            .all()
        )

    def get_confirmed_upcoming(self, db: Session):
        return (
            db.query(Reservation)
            .filter(Reservation.status == ReservationStatus.CONFIRMED)
            .order_by(Reservation.requested_date, Reservation.requested_time)
            .all()
        )

    def has_open_reservation(self, db: Session, enrollment_id: int, requested_date: str, requested_time: str):
        return (
            db.query(Reservation)
            .filter(
                Reservation.enrollment_id == enrollment_id,
                Reservation.requested_date == requested_date,
                Reservation.requested_time == requested_time,
                Reservation.status.in_((ReservationStatus.PENDING, ReservationStatus.CONFIRMED)),
            )
            .first()
            is not None
        )
