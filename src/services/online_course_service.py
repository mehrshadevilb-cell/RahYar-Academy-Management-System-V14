from sqlalchemy.orm import Session

from src.database.models.online_course import OnlineCourse
from src.database.repositories.online_course_repository import OnlineCourseRepository


class OnlineCourseService:
    """
    Admin CRUD for the online-class catalog (Arrangement, Mixing, Piano,
    etc). This only manages the course *template* - price, teacher,
    duration, session counts. Changing these values never retroactively
    changes an already-active `OnlineEnrollment` (its remaining_sessions
    and pricing were copied at enrollment time), which is intentional:
    a student mid-term should not be affected by a price/session change
    made after they enrolled.
    """

    # Whitelisted, typed fields an admin is allowed to edit. Keeping this
    # explicit (rather than setattr on any field name) prevents a UI bug
    # from ever writing to an unintended column.
    EDITABLE_FIELDS = {
        "name": str,
        "teacher": str,
        "duration_minutes": int,
        "monthly_price": int,
        "term_price": int,
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
    ) -> OnlineCourse:
        return self.repository.create(
            db,
            OnlineCourse(
                name=name,
                teacher=teacher,
                duration_minutes=duration_minutes,
                monthly_price=monthly_price,
                term_price=term_price,
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
