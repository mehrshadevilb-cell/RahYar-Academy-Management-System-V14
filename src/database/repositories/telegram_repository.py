from sqlalchemy.orm import Session, joinedload

from src.database.models.telegram_account import TelegramAccount



class TelegramRepository:


    def get_by_telegram_id(
        self,
        db: Session,
        telegram_id: str,
    ):

        return (
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



    def get_by_user_id(
        self,
        db: Session,
        user_id: int,
    ):

        return (
            db.query(TelegramAccount)
            .filter(
                TelegramAccount.user_id == user_id
            )
            .first()
        )



    def create(
        self,
        db: Session,
        account: TelegramAccount,
    ):

        db.add(account)

        db.commit()

        db.refresh(account)

        return account



    def get_all(
        self,
        db: Session,
    ):
        """All linked Telegram accounts - used as the broadcast audience."""

        return (
            db.query(TelegramAccount)
            .options(
                joinedload(
                    TelegramAccount.user
                )
            )
            .all()
        )