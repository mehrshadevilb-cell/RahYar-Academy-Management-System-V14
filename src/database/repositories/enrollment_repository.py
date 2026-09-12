from sqlalchemy.orm import Session

from src.database.models.enrollment import Enrollment



class EnrollmentRepository:



    def exists(
        self,
        db: Session,
        user_id: int,
        course_id: int,
    ):


        return (
            db.query(Enrollment)
            .filter(
                Enrollment.user_id == user_id,
                Enrollment.course_id == course_id,
            )
            .first()
            is not None
        )




    def create(
        self,
        db: Session,
        user_id: int,
        course_id: int,
    ):


        enrollment = Enrollment(
            user_id=user_id,
            course_id=course_id,
        )


        db.add(enrollment)

        db.commit()

        db.refresh(enrollment)


        return enrollment




    def get_user_courses(
        self,
        db: Session,
        user_id: int,
    ):


        return (
            db.query(Enrollment)
            .filter(
                Enrollment.user_id == user_id
            )
            .all()
        )