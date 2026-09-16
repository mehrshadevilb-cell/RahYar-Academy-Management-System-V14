from sqlalchemy.orm import Session

from src.database.repositories.profile_repository import ProfileRepository


class ProfileService:

    def __init__(self):
        self.repository = ProfileRepository()

    def get_profile(self, db: Session, telegram_id: str):
        return self.repository.get_user_by_telegram_id(db, telegram_id)

    def get_profile_by_id(self, db: Session, user_id: int):
        return self.repository.get_by_id(db, user_id)

    def get_profile_by_phone(self, db: Session, phone: str):
        return self.repository.get_by_phone(db, phone)

    def get_profile_by_student_number(self, db: Session, student_number: str):
        return self.repository.get_by_student_number(db, student_number)

    def list_students(self, db: Session, *, page: int = 0, page_size: int = 15):
        offset = max(page, 0) * page_size
        students = self.repository.list_students(db, offset=offset, limit=page_size)
        total = self.repository.count_students(db)
        return students, total

    def update_contact_info(self, db: Session, user, full_name: str, phone: str):
        return self.repository.update_contact_info(db, user, full_name, phone)
