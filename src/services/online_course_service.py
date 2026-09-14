from sqlalchemy.orm import Session

from src.database.models.online_course import OnlineCourse
from src.database.repositories.online_course_repository import OnlineCourseRepository


class OnlineCourseService:
    """
    Admin CRUD for the online-class catalog (Arrangement, Mixing, Piano,
    etc). This only manages the course *template* - price, teacher,
    duration, session counts. Changing these values never retroactively
    changes an already-active OnlineEnrollment.
    """

    EDITABLE_FIELDS = {
        "name": str,
        "teacher": str,
        "duration_minutes": int,
        "weekly_price": int,
        "monthly_price": int,
        "term_price": int,
        "weekly_sessions": int,
        "monthly_sessions": int,
        "term_sessions": int,
    }

    def __init__(self):
        self.repository = OnlineCourseRepository()

    def get_active_courses(self, db: Session):
        return self.repository.get_active(db)

    def get_all_courses(self, db: Session):
        return self.repository.get_all(db)

    def get_course_by_id(self, db: Session, course_id: int):
        return self.repository.get_by_id(db, course_id)

    def create_course(
        self,
        db: Session,
        name: str,
        teacher: str | None,
        duration_minutes: int,
        monthly_price: int | None,
        term_price: int | None,
        monthly_sessions: int,
        term_sessions: int,
        weekly_price: int | None = None,
        weekly_sessions: int = 1,
    ) -> OnlineCourse:
        return self.repository.create(
            db,
            OnlineCourse(
                name=name,
                teacher=teacher,
                duration_minutes=duration_minutes,
                weekly_price=weekly_price,
                monthly_price=monthly_price,
                term_price=term_price,
                weekly_sessions=weekly_sessions,
                monthly_sessions=monthly_sessions,
                term_sessions=term_sessions,
            ),
        )

    def update_field(self, db: Session, course_id: int, field: str, value):
        if field not in self.EDITABLE_FIELDS:
            raise ValueError(f"فیلد «{field}» قابل ویرایش نیست.")

        course = self.repository.get_by_id(db, course_id)
        if not course:
            return None

        setattr(course, field, self.EDITABLE_FIELDS[field](value))

        db.commit()
        db.refresh(course)
        return course

    def toggle_active(self, db: Session, course_id: int):
        course = self.repository.get_by_id(db, course_id)
        if not course:
            return None

        course.is_active = not course.is_active

        db.commit()
        db.refresh(course)
        return course
