from sqlalchemy.orm import Session

from src.database.models.class_slot import ClassSlot, ClassSlotStatus
from src.database.repositories.class_slot_repository import ClassSlotRepository


class ClassSlotService:
    def __init__(self):
        self.repository = ClassSlotRepository()

    def publish(
        self,
        db: Session,
        online_course_id: int,
        slot_date: str,
        slot_time: str,
        capacity: int = 1,
    ) -> ClassSlot:
        return self.repository.create(
            db,
            ClassSlot(
                online_course_id=online_course_id,
                slot_date=slot_date,
                slot_time=slot_time,
                capacity=max(1, capacity),
                status=ClassSlotStatus.OPEN,
            ),
        )

    def get_by_id(self, db: Session, slot_id: int) -> ClassSlot | None:
        return self.repository.get_by_id(db, slot_id)

    def get_open_by_course(self, db: Session, online_course_id: int) -> list[ClassSlot]:
        return self.repository.get_open_by_course(db, online_course_id)

    def get_open_all(self, db: Session) -> list[ClassSlot]:
        return self.repository.get_open_all(db)

    def list_active(self, db: Session) -> list[ClassSlot]:
        return self.repository.list_active(db)

    def list_by_course(self, db: Session, online_course_id: int) -> list[ClassSlot]:
        return self.repository.list_by_course(db, online_course_id)

    def close(self, db: Session, slot_id: int) -> ClassSlot | None:
        slot = self.repository.get_by_id(db, slot_id)
        if not slot:
            return None
        slot.status = ClassSlotStatus.CLOSED
        slot.is_active = False
        db.commit()
        db.refresh(slot)
        return slot

    def try_book(self, db: Session, slot: ClassSlot) -> bool:
        """Increment booked_count if capacity remains. Returns False if full."""
        if slot.status != ClassSlotStatus.OPEN or not slot.is_active:
            return False
        if slot.booked_count >= slot.capacity:
            return False
        slot.booked_count += 1
        if slot.booked_count >= slot.capacity:
            slot.status = ClassSlotStatus.BOOKED
        db.commit()
        db.refresh(slot)
        return True

    def release_book(self, db: Session, slot: ClassSlot) -> None:
        """Release one booking (e.g. reservation rejected/cancelled)."""
        if slot.booked_count > 0:
            slot.booked_count -= 1
        if slot.status == ClassSlotStatus.BOOKED and slot.booked_count < slot.capacity:
            slot.status = ClassSlotStatus.OPEN
        db.commit()
