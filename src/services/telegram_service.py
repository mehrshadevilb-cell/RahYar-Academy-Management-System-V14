from sqlalchemy.orm import Session

from src.database.repositories.telegram_repository import TelegramRepository
from src.services.canonical_identity_service import CanonicalIdentityService


class TelegramService:
    def __init__(self):
        self.repository = TelegramRepository()
        self.identity_service = CanonicalIdentityService()

    def get_or_create_user(
        self,
        db: Session,
        telegram_id: str,
        full_name: str,
        username: str | None,
    ):
        account = self.repository.get_by_telegram_id(db, telegram_id)
        if account:
            account.username = username
            if full_name:
                account.user.full_name = full_name[:100]
            db.commit()
            db.refresh(account.user)
            return account.user, False

        user = self.identity_service.link_telegram_account(
            db,
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
        )
        return user, True
