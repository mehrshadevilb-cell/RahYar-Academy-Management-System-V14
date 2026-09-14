from sqlalchemy.orm import Session

from src.database.models.class_slot import ClassSlot
from src.database.repositories.class_slot_repository import ClassSlotRepository


class ClassSlotServiceError(ValueError):
    pass


class ClassSlotService:

    def __init__(self) -> None:
        self.repository = ClassSlotRepository()

    def create_slot(
        self,
        db: Session,
        *,
        online_course_id: int,
        slot_date: str,
        slot_time: str,
        capacity: int = 1,
        notes: str | None = None,
    ) -> ClassSlot:
        slot_date = (slot_date or "").strip()
        slot_time = (slot_time or "").strip()
        if not slot_date or not slot_time:
            raise ClassSlotServiceError("invalid_slot")
        if capacity < 1:
            raise ClassSlotServiceError("invalid_capacity")

        return self.repository.create(
            db,
            ClassSlot(
                online_course_id=online_course_id,
                slot_date=slot_date,
                slot_time=slot_time,
                capacity=capacity,
                notes=notes,
            ),
        )

    def list_open_for_course(self, db: Session, online_course_id: int) -> list[ClassSlot]:
        return self.repository.list_open_for_course(db, online_course_id)

    def list_all_open(self, db: Session) -> list[ClassSlot]:
        return self.repository.list_all_open(db)

    def list_for_admin(self, db: Session) -> list[ClassSlot]:
        return self.repository.list_for_admin(db)

    def get(self, db: Session, slot_id: int) -> ClassSlot | None:
        return self.repository.get_by_id(db, slot_id)

    def close(self, db: Session, slot_id: int) -> ClassSlot:
        slot = self.repository.get_by_id(db, slot_id)
        if not slot:
            raise ClassSlotServiceError("not_found")
        return self.repository.close(db, slot)

    def book_slot(self, db: Session, slot_id: int) -> ClassSlot:
        slot = self.repository.get_by_id(db, slot_id)
        if not slot or not slot.is_available:
            raise ClassSlotServiceError("slot_unavailable")
        return self.repository.book(db, slot)
