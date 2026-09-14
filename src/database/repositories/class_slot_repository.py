from sqlalchemy.orm import Session

from src.database.models.class_slot import ClassSlot, ClassSlotStatus


class ClassSlotRepository:
    def create(self, db: Session, slot: ClassSlot) -> ClassSlot:
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

    def get_by_id(self, db: Session, slot_id: int) -> ClassSlot | None:
        return db.query(ClassSlot).filter(ClassSlot.id == slot_id).first()

    def get_open_by_course(self, db: Session, online_course_id: int) -> list[ClassSlot]:
        return (
            db.query(ClassSlot)
            .filter(
                ClassSlot.online_course_id == online_course_id,
                ClassSlot.is_active.is_(True),
                ClassSlot.status == ClassSlotStatus.OPEN,
            )
            .order_by(ClassSlot.slot_date, ClassSlot.slot_time)
            .all()
        )

    def get_open_all(self, db: Session) -> list[ClassSlot]:
        return (
            db.query(ClassSlot)
            .filter(
                ClassSlot.is_active.is_(True),
                ClassSlot.status == ClassSlotStatus.OPEN,
            )
            .order_by(ClassSlot.slot_date, ClassSlot.slot_time)
            .all()
        )

    def list_by_course(self, db: Session, online_course_id: int) -> list[ClassSlot]:
        return (
            db.query(ClassSlot)
            .filter(ClassSlot.online_course_id == online_course_id)
            .order_by(ClassSlot.slot_date.desc(), ClassSlot.slot_time)
            .all()
        )

    def list_active(self, db: Session) -> list[ClassSlot]:
        return (
            db.query(ClassSlot)
            .filter(ClassSlot.is_active.is_(True))
            .order_by(ClassSlot.slot_date, ClassSlot.slot_time)
            .all()
        )
