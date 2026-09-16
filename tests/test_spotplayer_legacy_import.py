from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.course import Course, ProductDeliveryType
from src.database.models.enrollment import Enrollment
from src.database.models.license import License
from src.database.models.user import User
from src.services.spotplayer_legacy_import_service import (
    SpotPlayerLegacyImportService,
    normalize_iran_phone,
)

# Import related models so metadata is complete.
from src.database.models.telegram_account import TelegramAccount  # noqa: F401
from src.database.models.payment import Payment  # noqa: F401
from src.database.models.spotplayer_course import SpotPlayerCourse  # noqa: F401


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_products(db):
    theory = Course(title="تئوری موسیقی", price=380_000, delivery_type=ProductDeliveryType.SPOTPLAYER)
    rahyar = Course(title="راه‌یار", price=15_000_000, delivery_type=ProductDeliveryType.SPOTPLAYER)
    db.add_all([theory, rahyar])
    db.commit()
    return theory, rahyar


def test_normalize_phone_variants():
    assert normalize_iran_phone("9125593083") == "09125593083"
    assert normalize_iran_phone("+98 922 631 1265") == "09226311265"
    assert normalize_iran_phone("989194942793") == "09194942793"
    assert normalize_iran_phone("09396951561") == "09396951561"
    assert normalize_iran_phone("09000000000") is None
    assert normalize_iran_phone("Mehrshad") is None


def test_import_creates_user_enrollment_license():
    db = make_db()
    theory, rahyar = seed_products(db)
    service = SpotPlayerLegacyImportService()

    result = service.import_row(
        db,
        name="مهدی تست",
        watermark="9125593083",
        course_cell="تئوری موسیقی,راه‌یار ِ تنظیم، میکس و مسترینگ",
        spotplayer_id="abc123",
        license_key="key-abc",
        created_at=datetime(2026, 1, 1),
        dry_run=False,
    )
    db.commit()

    assert result.status == "imported"
    user = db.query(User).filter(User.phone == "09125593083").one()
    assert user.full_name == "مهدی تست"
    assert user.telegram_account is None
    assert db.query(Enrollment).filter(Enrollment.user_id == user.id).count() == 2
    licenses = db.query(License).filter(License.user_id == user.id, License.status == "active").all()
    assert len(licenses) == 2
    assert {lic.product_id for lic in licenses} == {theory.id, rahyar.id}
    assert all(lic.license_key == "key-abc" for lic in licenses)


def test_import_is_idempotent():
    db = make_db()
    seed_products(db)
    service = SpotPlayerLegacyImportService()
    kwargs = dict(
        name="مهدی تست",
        watermark="9125593083",
        course_cell="تئوری موسیقی",
        spotplayer_id="abc123",
        license_key="key-abc",
        dry_run=False,
    )
    service.import_row(db, **kwargs)
    db.commit()
    service.import_row(db, **kwargs)
    db.commit()
    assert db.query(User).count() == 1
    assert db.query(Enrollment).count() == 1
    assert db.query(License).count() == 1


def test_unmapped_course_is_skipped():
    db = make_db()
    seed_products(db)
    service = SpotPlayerLegacyImportService()
    result = service.import_row(
        db,
        name="X",
        watermark="9125593083",
        course_cell="کیوبیس - Cubase (مهرشاد بنائی)",
        spotplayer_id="id1",
        license_key="k1",
        dry_run=False,
    )
    assert result.status == "skipped"
    assert db.query(User).count() == 0
