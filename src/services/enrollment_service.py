from sqlalchemy.orm import Session

from src.database.models.enrollment import Enrollment
from src.database.models.course import Course
from src.database.models.user import User


class EnrollmentService:


    def create_enrollment(
        self,
        db: Session,
        user_id: int,
        course_id: int,
    ):

        exists = (
            db.query(Enrollment)
            .filter(
                Enrollment.user_id == user_id,
                Enrollment.course_id == course_id,
            )
            .first()
        )


        if exists:
            return exists



        enrollment = Enrollment(
            user_id=user_id,
            course_id=course_id,
        )


        db.add(enrollment)

        db.commit()

        db.refresh(
            enrollment
        )


        return enrollment



    def get_user_courses(
        self,
        db: Session,
        user_id: int,
    ):


        courses = (
            db.query(Course)
            .join(
                Enrollment,
                Enrollment.course_id == Course.id
            )
            .filter(
                Enrollment.user_id == user_id
            )
            .all()
        )


        return courses