from sqlalchemy.orm import Session

from src.database.models.reservation import Reservation, ReservationStatus
from src.database.repositories.reservation_repository import ReservationRepository


class ReservationService:
    def __init__(self):
        self.repository = ReservationRepository()

    def request_reservation(self, db: Session, enrollment_id: int, requested_date: str, requested_time: str):
        if self.repository.has_open_reservation(db, enrollment_id, requested_date, requested_time):
            return None

        reservation = Reservation(
            enrollment_id=enrollment_id,
            requested_date=requested_date,
            requested_time=requested_time,
            status=ReservationStatus.WAITING_PAYMENT,
        )
        return self.repository.create(db, reservation)

    def submit_payment(self, db: Session, reservation_id: int, proof: str):
        reservation = self.repository.get_by_id(db, reservation_id)
        if reservation:
            reservation.payment_proof = proof
            reservation.status = ReservationStatus.PAYMENT_SUBMITTED
            db.commit()
            db.refresh(reservation)
        return reservation

    def confirm(self, db: Session, reservation_id: int):
        reservation = self.repository.get_by_id(db, reservation_id)
        if not reservation:
            return None
        if reservation.status not in (
            ReservationStatus.PAYMENT_SUBMITTED,
            ReservationStatus.PENDING,
        ):
            return reservation
        reservation.status = ReservationStatus.CONFIRMED
        db.commit()
        db.refresh(reservation)
        return reservation

    def reject(self, db: Session, reservation_id: int, notes=None):
        reservation = self.repository.get_by_id(db, reservation_id)
        if reservation:
            reservation.status = ReservationStatus.REJECTED
            reservation.admin_notes = notes
            db.commit()
            db.refresh(reservation)
        return reservation

    def get_by_id(self, db: Session, reservation_id: int):
        return self.repository.get_by_id(db, reservation_id)

    def get_pending(self, db: Session):
        return self.repository.get_pending(db)
