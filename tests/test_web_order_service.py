import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.course import Course, ProductDeliveryType
from src.services.web_order_service import WebOrderError, WebOrderService


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_product_order_pending():
    db = make_db()
    product = Course(
        title="Theory Pack",
        description="desc",
        price=1_500_000,
        delivery_type=ProductDeliveryType.SPOTPLAYER,
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    service = WebOrderService()
    user, payment, ordered = service.create_product_order(
        db,
        product_id=product.id,
        full_name="علی تست",
        phone="09121234567",
    )

    assert ordered.id == product.id
    assert user.phone == "09121234567"
    assert payment.status == "pending"
    assert payment.amount == 1_500_000
    assert payment.receipt_file_id.startswith("web:")


def test_invalid_phone():
    db = make_db()
    service = WebOrderService()
    with pytest.raises(WebOrderError, match="invalid_phone"):
        service.normalize_phone("123")


def test_order_status_requires_matching_phone():
    db = make_db()
    product = Course(
        title="Mix Pack",
        description="desc",
        price=2_000_000,
        delivery_type=ProductDeliveryType.TELEGRAM,
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    service = WebOrderService()
    user, payment, _ = service.create_product_order(
        db,
        product_id=product.id,
        full_name="هنرجوی وضعیت",
        phone="09121234567",
    )

    result = service.get_product_order_status(
        db,
        payment_id=payment.id,
        phone="+989121234567",
    )
    assert result is not None
    matched_user, matched_payment, matched_product = result
    assert matched_user.id == user.id
    assert matched_payment.id == payment.id
    assert matched_product.id == product.id

    assert service.get_product_order_status(
        db,
        payment_id=payment.id,
        phone="09120000000",
    ) is None
