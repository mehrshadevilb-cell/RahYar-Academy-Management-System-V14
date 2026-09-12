from sqlalchemy.orm import Session

from src.database.models.telegram_account import TelegramAccount
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.user_service import UserService



class TelegramService:


    def __init__(self):

        self.repository = TelegramRepository()

        self.user_service = UserService()



    def get_or_create_user(
        self,
        db: Session,
        telegram_id: str,
        full_name: str,
        username: str | None,
    ):


        account = self.repository.get_by_telegram_id(
            db,
            telegram_id,
        )


        if account:

            return account.user, False



        user = self.user_service.create_student(
            db,
            full_name,
        )


        account = TelegramAccount(
            user_id=user.id,
            telegram_id=telegram_id,
            username=username,
        )


        self.repository.create(
            db,
            account,
        )


        return user, True