from sqlalchemy.orm import Session

from src.database.models.class_slot import ClassSlot


class ClassSlotRepository:

    def create(self, db: Session, slot: ClassSlot) -> ClassSlot:
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

    def get_by_id(self, db: Session, slot_id: int) -> ClassSlot | None:
        return db.query(ClassSlot).filter(ClassSlot.id == slot_id).first()

    def list_open_for_course(self, db: Session, online_course_id: int) -> list[ClassSlot]:
        slots = (
            db.query(ClassSlot)
            .filter(
                ClassSlot.online_course_id == online_course_id,
                ClassSlot.is_open.is_(True),
            )
            .order_by(ClassSlot.slot_date, ClassSlot.slot_time)
            .all()
        )
        return [s for s in slots if s.is_available]

    def list_all_open(self, db: Session, limit: int = 50) -> list[ClassSlot]:
        slots = (
            db.query(ClassSlot)
            .filter(ClassSlot.is_open.is_(True))
            .order_by(ClassSlot.slot_date, ClassSlot.slot_time)
            .limit(limit)
            .all()
        )
        return [s for s in slots if s.is_available]

    def list_for_admin(self, db: Session, limit: int = 40) -> list[ClassSlot]:
        return (
            db.query(ClassSlot)
            .order_by(ClassSlot.id.desc())
            .limit(limit)
            .all()
        )

    def close(self, db: Session, slot: ClassSlot) -> ClassSlot:
        slot.is_open = False
        db.commit()
        db.refresh(slot)
        return slot

    def book(self, db: Session, slot: ClassSlot) -> ClassSlot:
        if not slot.is_available:
            raise ValueError("slot_full")
        slot.booked_count += 1
        if slot.booked_count >= slot.capacity:
            slot.is_open = False
        db.commit()
        db.refresh(slot)
        return slot
