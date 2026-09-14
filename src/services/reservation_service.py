from sqlalchemy.orm import Session

from src.database.models.reservation import Reservation, ReservationStatus
from src.database.repositories.reservation_repository import ReservationRepository
from src.services.class_slot_service import ClassSlotService, ClassSlotServiceError


class ReservationService:
    def __init__(self):
        self.repository = ReservationRepository()
        self.slot_service = ClassSlotService()

    def request_reservation(
        self, db: Session, enrollment_id: int, requested_date: str, requested_time: str
    ) -> Reservation | None:
        if self.repository.has_open_reservation(
            db, enrollment_id, requested_date, requested_time
        ):
            return None

        return self.repository.create(
            db,
            Reservation(
                enrollment_id=enrollment_id,
                requested_date=requested_date,
                requested_time=requested_time,
            ),
        )

    def request_from_slot(
        self, db: Session, enrollment_id: int, slot_id: int
    ) -> Reservation:
        """Book an owner-published slot and create a pending reservation."""
        slot = self.slot_service.get(db, slot_id)
        if not slot or not slot.is_available:
            raise ClassSlotServiceError("slot_unavailable")

        if self.repository.has_open_reservation(
            db, enrollment_id, slot.slot_date, slot.slot_time
        ):
            raise ClassSlotServiceError("already_requested")

        self.slot_service.book_slot(db, slot_id)

        return self.repository.create(
            db,
            Reservation(
                enrollment_id=enrollment_id,
                requested_date=slot.slot_date,
                requested_time=slot.slot_time,
            ),
        )

    def confirm(self, db: Session, reservation_id: int) -> Reservation | None:
        reservation = self.repository.get_by_id(db, reservation_id)
        if not reservation or reservation.status != ReservationStatus.PENDING:
            return reservation
        reservation.status = ReservationStatus.CONFIRMED
        db.commit()
        db.refresh(reservation)
        return reservation

    def reject(self, db: Session, reservation_id: int, notes: str | None = None) -> Reservation | None:
        reservation = self.repository.get_by_id(db, reservation_id)
        if not reservation or reservation.status != ReservationStatus.PENDING:
            return reservation
        reservation.status = ReservationStatus.REJECTED
        reservation.admin_notes = notes
        db.commit()
        db.refresh(reservation)
        return reservation

    def cancel(self, db: Session, reservation_id: int) -> Reservation | None:
        reservation = self.repository.get_by_id(db, reservation_id)
        if not reservation:
            return None
        if reservation.status not in (
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
        ):
            return reservation
        reservation.status = ReservationStatus.CANCELLED
        db.commit()
        db.refresh(reservation)
        return reservation

    def complete(self, db: Session, reservation_id: int) -> Reservation | None:
        reservation = self.repository.get_by_id(db, reservation_id)
        if not reservation:
            return None
        reservation.status = ReservationStatus.COMPLETED
        db.commit()
        db.refresh(reservation)
        return reservation

    def get_by_id(self, db: Session, reservation_id: int):
        return self.repository.get_by_id(db, reservation_id)

    def get_pending(self, db: Session):
        return self.repository.get_pending(db)
