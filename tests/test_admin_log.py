from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.admin_log import AdminLog
from src.services.admin_log_service import AdminLogService


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_log_creates_a_record_with_string_admin_id():
    db = make_db()
    service = AdminLogService()

    log = service.log(db, admin_telegram_id=123456789, action="product_toggle", description="test")

    assert log.id is not None
    assert log.admin_telegram_id == "123456789"  # stored as string
    assert log.action == "product_toggle"


def test_get_recent_returns_newest_first():
    db = make_db()
    service = AdminLogService()

    service.log(db, 1, "a", "اولین رویداد")
    service.log(db, 1, "b", "دومین رویداد")
    service.log(db, 1, "c", "سومین رویداد")

    recent = service.get_recent(db, limit=2)

    assert len(recent) == 2
    assert recent[0].description == "سومین رویداد"
    assert recent[1].description == "دومین رویداد"


def test_search_matches_description_and_action():
    db = make_db()
    service = AdminLogService()

    service.log(db, 1, "payment_approve", "پرداخت #12 تایید شد")
    service.log(db, 1, "payment_reject", "پرداخت #13 رد شد")
    service.log(db, 1, "discount_code_create", "کد تخفیف SUMMER30 ساخته شد")

    by_description = service.search(db, "پرداخت")
    assert len(by_description) == 2

    by_action = service.search(db, "discount_code")
    assert len(by_action) == 1
    assert "SUMMER30" in by_action[0].description

    no_match = service.search(db, "چیزی که وجود ندارد")
    assert no_match == []
