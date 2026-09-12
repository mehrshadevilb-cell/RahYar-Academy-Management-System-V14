from sqlalchemy.orm import Session

from src.database.models.user import User, UserRole
from src.database.repositories.user_repository import UserRepository


class UserService:


    def __init__(self):

        self.repository = UserRepository()



    def create_student(
        self,
        db: Session,
        full_name: str,
    ):

        user = User(
            full_name=full_name,
            role=UserRole.STUDENT,
            is_active=True,
        )


        return self.repository.create(
            db,
            user,
        )