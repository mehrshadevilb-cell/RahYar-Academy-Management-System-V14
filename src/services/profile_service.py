from sqlalchemy.orm import Session

from src.database.repositories.profile_repository import ProfileRepository



class ProfileService:


    def __init__(self):

        self.repository = ProfileRepository()



    def get_profile(
        self,
        db: Session,
        telegram_id: str,
    ):

        return self.repository.get_user_by_telegram_id(
            db,
            telegram_id,
        )


    def get_profile_by_id(
        self,
        db: Session,
        user_id: int,
    ):

        return self.repository.get_by_id(
            db,
            user_id,
        )


    def get_profile_by_phone(
        self,
        db: Session,
        phone: str,
    ):

        return self.repository.get_by_phone(
            db,
            phone,
        )


    def update_contact_info(
        self,
        db: Session,
        user,
        full_name: str,
        phone: str,
    ):

        return self.repository.update_contact_info(
            db,
            user,
            full_name,
            phone,
        )
