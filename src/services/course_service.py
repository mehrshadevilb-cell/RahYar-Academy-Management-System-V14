from sqlalchemy.orm import Session

from src.database.repositories.course_repository import CourseRepository



class CourseService:



    def __init__(self):

        self.repository = CourseRepository()



    def get_courses(
        self,
        db: Session,
    ):


        return self.repository.get_active_courses(
            db
        )


    def get_course_by_id(
        self,
        db: Session,
        course_id: int,
    ):

        return self.repository.get_by_id(
            db,
            course_id,
        )


    def get_all_courses(
        self,
        db: Session,
    ):

        return self.repository.get_all(db)


    def toggle_active(
        self,
        db: Session,
        course_id: int,
    ):

        course = self.repository.get_by_id(db, course_id)

        if not course:
            return None

        course.is_active = not course.is_active

        db.commit()
        db.refresh(course)

        return course


    def update_price(
        self,
        db: Session,
        course_id: int,
        new_price: int,
    ):

        course = self.repository.get_by_id(db, course_id)

        if not course:
            return None

        course.price = new_price

        db.commit()
        db.refresh(course)

        return course
