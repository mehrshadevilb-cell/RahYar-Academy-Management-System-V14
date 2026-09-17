import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.student_profile import StudentProfile
from src.database.models.user import User, UserRole
from src.core.security.password import verify_password
from src.services.web_registration_service import WebRegistrationError, WebRegistrationService


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_first_website_registration_claims_unlinked_spotplayer_record():
    db = make_db()
    imported = User(full_name="نام قدیمی", phone="09121234567", role=UserRole.STUDENT, password_hash=None)
    db.add(imported)
    db.commit()

    result = WebRegistrationService().register(
        db,
        full_name="هنرجوی جدید",
        phone="+989121234567",
        password="strong-password",
    )

    assert result.claimed_existing_record is True
    assert result.user.id == imported.id
    assert result.user.full_name == "هنرجوی جدید"
    assert result.user.password_hash
    assert verify_password("strong-password", result.user.password_hash)
    assert db.query(User).filter(User.phone == "09121234567").count() == 1
    assert db.query(StudentProfile).filter(StudentProfile.user_id == imported.id).count() == 1


def test_real_existing_website_account_rejects_duplicate_phone_registration():
    db = make_db()
    service = WebRegistrationService()
    service.register(db, full_name="اولی", phone="09121234567", password="strong-password")

    with pytest.raises(WebRegistrationError, match="phone_already_registered"):
        service.register(db, full_name="دومی", phone="09121234567", password="another-password")
