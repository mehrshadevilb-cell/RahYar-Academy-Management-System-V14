from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User
from src.services.canonical_identity_service import CanonicalIdentityService

# Register every model with Base.metadata before creating the test schema.
import src.database.init_db  # noqa: F401,E402


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_phone_normalization_is_canonical():
    service = CanonicalIdentityService()
    assert service.normalize_phone("+989121234567") == "09121234567"
    assert service.normalize_phone("09121234567") == "09121234567"
    assert service.normalize_phone("123") is None


def test_link_telegram_merges_unlinked_website_lead():
    db = make_db()
    legacy = User(full_name="Website Lead", phone="09121234567")
    db.add(legacy)
    db.commit()

    user = CanonicalIdentityService().link_telegram_account(
        db,
        telegram_id="998877",
        full_name="Telegram Student",
        phone="+989121234567",
        username="student",
    )

    assert user.phone == "09121234567"
    assert user.full_name == "Telegram Student"
    assert user.telegram_account.telegram_id == "998877"
    assert db.query(User).filter(User.id == legacy.id).one_or_none() is None
    assert db.query(TelegramAccount).filter(TelegramAccount.telegram_id == "998877").count() == 1
