from sqlalchemy.orm import Session

from src.database.models.online_course import OnlineCourse


class OnlineCourseRepository:

    def get_active(self, db: Session):
        return (
            db.query(OnlineCourse)
            .filter(OnlineCourse.is_active == True)
            .order_by(OnlineCourse.id)
            .all()
        )

    def get_by_id(self, db: Session, course_id: int):
        return (
            db.query(OnlineCourse)
            .filter(OnlineCourse.id == course_id)
            .first()
        )

    def get_all(self, db: Session):
        return (
            db.query(OnlineCourse)
            .order_by(OnlineCourse.id)
            .all()
        )

    def create(self, db: Session, course: OnlineCourse):
        db.add(course)
        db.commit()
        db.refresh(course)
        return course
