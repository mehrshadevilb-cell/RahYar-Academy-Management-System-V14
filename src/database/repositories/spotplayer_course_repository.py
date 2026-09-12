from sqlalchemy.orm import Session

from src.database.models.spotplayer_course import SpotPlayerCourse


class SpotPlayerCourseRepository:

    def get_by_id(self, db: Session, record_id: int):
        return (
            db.query(SpotPlayerCourse)
            .filter(SpotPlayerCourse.id == record_id)
            .first()
        )

    def get_by_product(self, db: Session, product_id: int):
        return (
            db.query(SpotPlayerCourse)
            .filter(SpotPlayerCourse.product_id == product_id)
            .order_by(SpotPlayerCourse.sort_order, SpotPlayerCourse.id)
            .all()
        )

    def create(self, db: Session, record: SpotPlayerCourse):
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def delete(self, db: Session, record: SpotPlayerCourse):
        db.delete(record)
        db.commit()
