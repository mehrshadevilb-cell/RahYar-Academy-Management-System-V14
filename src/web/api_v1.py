"""JSON API for the ArtistYar Next.js website.

Shares the same PostgreSQL database and payment rules as the Telegram bot:
website can create pending orders/inquiries; access is never granted until
the owner approves in Telegram.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.bot.bot import bot
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.services.web_order_service import WebOrderError, WebOrderService
from src.web.deps import get_db

logger = get_logger("web.api_v1")
settings = get_settings()
order_service = WebOrderService()

router = APIRouter(prefix="/api/v1", tags=["artistyar-api"])


class ProductOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    price: int
    is_active: bool = True


class ClassOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool = True


class OrderIn(BaseModel):
    product_id: int
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class InquiryIn(BaseModel):
    course_id: int
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    message: str | None = Field(default=None, max_length=1000)


class OrderStatusOut(BaseModel):
    payment_id: int
    product_title: str
    amount: int
    status: str
    created_at: str


@router.get("/health")
async def api_v1_health():
    return {
        "ok": True,
        "service": "rahyar-api-v1",
        "site": settings.SITE_NAME,
    }


@router.get("/products", response_model=list[ProductOut])
async def list_products(db: Session = Depends(get_db)):
    try:
        products = order_service.list_products(db)
    except Exception:
        logger.exception("api_v1 list_products failed")
        raise HTTPException(status_code=503, detail="products_unavailable") from None
    return [
        ProductOut(
            id=p.id,
            title=p.title,
            description=getattr(p, "description", None),
            price=int(p.price or 0),
            is_active=bool(p.is_active),
        )
        for p in products
    ]


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = order_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="product_not_found")
    return ProductOut(
        id=product.id,
        title=product.title,
        description=getattr(product, "description", None),
        price=int(product.price or 0),
        is_active=bool(product.is_active),
    )


@router.get("/classes", response_model=list[ClassOut])
async def list_classes(db: Session = Depends(get_db)):
    try:
        classes = order_service.list_online_classes(db)
    except Exception:
        logger.exception("api_v1 list_classes failed")
        raise HTTPException(status_code=503, detail="classes_unavailable") from None
    return [
        ClassOut(
            id=c.id,
            name=c.name,
            description=getattr(c, "description", None),
            is_active=bool(c.is_active),
        )
        for c in classes
    ]


@router.post("/orders")
async def create_order(body: OrderIn, db: Session = Depends(get_db)):
    try:
        user, payment, product = order_service.create_product_order(
            db,
            product_id=body.product_id,
            full_name=body.full_name,
            phone=body.phone,
            note=body.note,
        )
    except WebOrderError as exc:
        mapping = {
            "invalid_phone": "شماره موبایل معتبر نیست.",
            "invalid_name": "نام را کامل وارد کنید.",
            "product_unavailable": "محصول در دسترس نیست.",
        }
        raise HTTPException(
            status_code=400,
            detail=mapping.get(str(exc), "ثبت سفارش ناموفق بود."),
        ) from exc

    if settings.OWNER_ID:
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    "🛒 سفارش API از سایت آرتیست‌یار\n\n"
                    f"محصول: {product.title}\n"
                    f"مبلغ: {payment.amount:,} تومان\n"
                    f"هنرجو: {user.full_name}\n"
                    f"موبایل: {user.phone}\n"
                    f"پرداخت #{payment.id} — pending\n"
                    "پس از رسید در پنل تلگرام تأیید کنید."
                ),
            )
        except Exception:
            logger.exception("Failed owner notify for API order %s", payment.id)

    card = order_service.get_active_card(db)
    return {
        "ok": True,
        "payment_id": payment.id,
        "amount": payment.amount,
        "status": payment.status,
        "product_title": product.title,
        "card": {
            "number": card.card_number if card else None,
            "holder": card.card_holder if card else None,
        },
        "message": "سفارش ثبت شد و در انتظار تأیید ادمین است.",
    }


@router.get("/orders/{payment_id}/status", response_model=OrderStatusOut)
async def order_status(
    payment_id: int,
    phone: str = Query(min_length=10, max_length=20),
    db: Session = Depends(get_db),
):
    try:
        result = order_service.get_product_order_status(
            db,
            payment_id=payment_id,
            phone=phone,
        )
    except WebOrderError as exc:
        if str(exc) == "invalid_phone":
            raise HTTPException(status_code=400, detail="invalid_phone") from exc
        raise

    if not result:
        raise HTTPException(status_code=404, detail="order_not_found")

    _, payment, product = result
    return OrderStatusOut(
        payment_id=payment.id,
        product_title=product.title,
        amount=int(payment.amount or 0),
        status=str(payment.status),
        created_at=payment.created_at.isoformat(),
    )


@router.post("/class-inquiries")
async def class_inquiry(body: InquiryIn, db: Session = Depends(get_db)):
    course = order_service.get_online_class(db, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="class_not_found")
    try:
        user = order_service.ensure_user(db, full_name=body.full_name, phone=body.phone)
    except WebOrderError as exc:
        mapping = {
            "invalid_phone": "شماره موبایل معتبر نیست.",
            "invalid_name": "نام را کامل وارد کنید.",
        }
        raise HTTPException(
            status_code=400,
            detail=mapping.get(str(exc), "ثبت درخواست ناموفق بود."),
        ) from exc

    if settings.OWNER_ID:
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    "🎼 درخواست کلاس از API آرتیست‌یار\n\n"
                    f"کلاس: {course.name}\n"
                    f"هنرجو: {user.full_name}\n"
                    f"موبایل: {user.phone}\n"
                    f"پیام: {(body.message or '—')[:500]}"
                ),
            )
        except Exception:
            logger.exception("Failed owner notify for class inquiry")

    return {
        "ok": True,
        "course_name": course.name,
        "message": "درخواست ثبت شد. ادمین از پنل تلگرام پیگیری می‌کند.",
    }
