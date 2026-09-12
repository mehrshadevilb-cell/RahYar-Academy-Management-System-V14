from sqlalchemy.orm import Session

from src.database.repositories.enrollment_repository import EnrollmentRepository
from src.database.models.course import Course



class StudentCourseService:



    def __init__(self):

        self.repository = EnrollmentRepository()



    def get_my_courses(
        self,
        db: Session,
        user_id: int,
    ):


        enrollments = self.repository.get_user_courses(
            db,
            user_id,
        )


        courses = []


        for item in enrollments:


            course = (
                db.query(Course)
                .filter(
                    Course.id == item.course_id
                )
                .first()
            )


            if course:

                courses.append(course)



        return courses