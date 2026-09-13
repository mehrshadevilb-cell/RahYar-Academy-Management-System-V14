from sqlalchemy.orm import Session, joinedload

from src.database.models.telegram_account import TelegramAccount


class ProfileRepository:


    def get_user_by_telegram_id(
        self,
        db: Session,
        telegram_id: str,
    ):

        account = (
            db.query(TelegramAccount)
            .options(
                joinedload(
                    TelegramAccount.user
                )
            )
            .filter(
                TelegramAccount.telegram_id == telegram_id
            )
            .first()
        )


        if not account:
            return None


        return account.user


    def get_by_id(
        self,
        db: Session,
        user_id: int,
    ):

        from src.database.models.user import User

        return (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )


    def get_by_phone(
        self,
        db: Session,
        phone: str,
    ):

        from src.database.models.user import User

        return (
            db.query(User)
            .filter(User.phone == phone)
            .first()
        )


    def update_contact_info(
        self,
        db: Session,
        user,
        full_name: str,
        phone: str,
    ):

        user.full_name = full_name
        user.phone = phone

        db.commit()
        db.refresh(user)

        return user
