from sqlalchemy.orm import Session

from src.database.models.user import User


class UserRepository:


    def get_by_id(
        self,
        db: Session,
        user_id: int,
    ):

        return (
            db.query(User)
            .filter(
                User.id == user_id
            )
            .first()
        )



    def get_by_full_name(
        self,
        db: Session,
        full_name: str,
    ):

        return (
            db.query(User)
            .filter(
                User.full_name == full_name
            )
            .first()
        )



    def create(
        self,
        db: Session,
        user: User,
    ):

        db.add(user)

        db.commit()

        db.refresh(user)

        return user