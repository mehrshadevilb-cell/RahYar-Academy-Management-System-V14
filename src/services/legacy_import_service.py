"""Compatibility facade for importing website leads into Telegram users."""

from sqlalchemy.orm import Session

from src.database.models.user import User
from src.services.canonical_identity_service import CanonicalIdentityService


class LegacyImportService:
    """Preserves the old handler API while using the canonical merge path."""

    def __init__(self) -> None:
        self.identity_service = CanonicalIdentityService()

    def find_unlinked_by_phone(self, db: Session, phone: str) -> User | None:
        normalized = self.identity_service.normalize_phone(phone)
        if not normalized:
            return None
        candidate = db.query(User).filter(User.phone == normalized).first()
        if candidate and candidate.telegram_account is None:
            return candidate
        return None

    def merge_into_live_user(self, db: Session, legacy_user: User, live_user: User) -> None:
        self.identity_service.merge_users(
            db,
            source=legacy_user,
            destination=live_user,
            commit=True,
        )
