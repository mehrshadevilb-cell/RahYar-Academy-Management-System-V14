from sqlalchemy.orm import Session, joinedload

from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User, UserRole


class ProfileRepository:

    def get_user_by_telegram_id(self, db: Session, telegram_id: str):
        account = (
            db.query(TelegramAccount)
            .options(joinedload(TelegramAccount.user))
            .filter(TelegramAccount.telegram_id == telegram_id)
            .first()
        )
        if not account:
            return None
        return account.user

    def get_by_id(self, db: Session, user_id: int):
        return db.query(User).filter(User.id == user_id).first()

    def get_by_phone(self, db: Session, phone: str):
        return db.query(User).filter(User.phone == phone).first()

    def get_by_student_number(self, db: Session, student_number: str):
        """Resolve the public student number shown by the bot.

        Student numbers are derived from the immutable user id.
        Both RH000123 and the bare numeric id are accepted.
        """
        value = (student_number or "").strip().upper()
        if value.startswith("RH"):
            value = value[2:]
        if not value.isdigit():
            return None
        return db.query(User).filter(User.id == int(value)).first()

    def list_students(self, db: Session, *, offset: int = 0, limit: int = 20) -> list[User]:
        """Active students ordered by full name for admin button pickers."""
        return (
            db.query(User)
            .filter(User.role == UserRole.STUDENT, User.is_active.is_(True))
            .order_by(User.full_name.asc(), User.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_students(self, db: Session) -> int:
        return (
            db.query(User)
            .filter(User.role == UserRole.STUDENT, User.is_active.is_(True))
            .count()
        )

    def update_contact_info(self, db: Session, user, full_name: str, phone: str):
        user.full_name = full_name
        user.phone = phone
        db.commit()
        db.refresh(user)
        return user
