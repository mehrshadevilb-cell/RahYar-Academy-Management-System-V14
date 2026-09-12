from sqlalchemy.orm import Session

from src.database.models.course import Course



class CourseRepository:


    def get_active_courses(
        self,
        db: Session,
    ):

        return (
            db.query(Course)
            .filter(
                Course.is_active == True
            )
            .order_by(
                Course.sort_order,
                Course.id,
            )
            .all()
        )


    def get_by_id(
        self,
        db: Session,
        course_id: int,
    ):

        return (
            db.query(Course)
            .filter(
                Course.id == course_id
            )
            .first()
        )


    def get_all(
        self,
        db: Session,
    ):

        return (
            db.query(Course)
            .order_by(
                Course.sort_order,
                Course.id,
            )
            .all()
        )
