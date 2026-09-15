from sqlalchemy.orm import Session

from src.database.models.reservation import Reservation, ReservationStatus


# Statuses that still occupy a slot for a given enrollment+date+time.
# Includes the payment-gate states so a second request cannot slip through
# while the student is still paying or waiting for admin confirmation.
_OPEN_STATUSES = (
    ReservationStatus.WAITING_PAYMENT,
    ReservationStatus.PAYMENT_SUBMITTED,
    ReservationStatus.PENDING,
    ReservationStatus.CONFIRMED,
)

# Reservations the admin must review (receipt uploaded, or legacy pending).
_PENDING_REVIEW_STATUSES = (
    ReservationStatus.PAYMENT_SUBMITTED,
    ReservationStatus.PENDING,
)


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
            .filter(Reservation.status.in_(_PENDING_REVIEW_STATUSES))
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
                Reservation.status.in_(_OPEN_STATUSES),
            )
            .first()
            is not None
        )
