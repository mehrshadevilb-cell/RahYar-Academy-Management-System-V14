"""Student product-course listing — delegates to EnrollmentService.

Previously duplicated the same join logic as EnrollmentService.get_user_courses.
One implementation path only.
"""
from sqlalchemy.orm import Session

from src.services.enrollment_service import EnrollmentService


class StudentCourseService:
    def __init__(self) -> None:
        self._enrollment_service = EnrollmentService()

    def get_my_courses(self, db: Session, user_id: int):
        return self._enrollment_service.get_user_courses(db, user_id)
