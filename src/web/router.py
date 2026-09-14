from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.bot.bot import bot
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.services.web_order_service import WebOrderError, WebOrderService
from src.web.deps import get_db

logger = get_logger("web.storefront")
settings = get_settings()
order_service = WebOrderService()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["storefront"])


def _bot_link(payload: str | None = None) -> str | None:
    base = settings.bot_deep_link_base
    if not base:
        return None
    if payload:
        return f"{base}?start={payload}"
    return base


def _ctx(request: Request, **extra):
    return {
        "request": request,
        "site_name": settings.SITE_NAME,
        "site_tagline": settings.SITE_TAGLINE,
        "bot_link": _bot_link(),
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    products = order_service.list_products(db)[:6]
    classes = order_service.list_online_classes(db)[:6]
    return templates.TemplateResponse(
        "home.html",
        _ctx(request, products=products, classes=classes),
    )


@router.get("/products", response_class=HTMLResponse)
async def products_list(request: Request, db: Session = Depends(get_db)):
    products = order_service.list_products(db)
    return templates.TemplateResponse(
        "products.html",
        _ctx(request, products=products),
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
async def product_detail(
    request: Request, product_id: int, db: Session = Depends(get_db)
):
    product = order_service.get_product(db, product_id)
    if not product:
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, message="محصول پیدا نشد یا غیرفعال است."),
            status_code=404,
        )
    card = order_service.get_active_card(db)
    return templates.TemplateResponse(
        "product_detail.html",
        _ctx(
            request,
            product=product,
            card=card,
            bot_buy_link=_bot_link(f"buy_{product.id}"),
        ),
    )


@router.post("/products/{product_id}/order", response_class=HTMLResponse)
async def product_order(
    request: Request,
    product_id: int,
    full_name: str = Form(...),
    phone: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        user, payment, product = order_service.create_product_order(
            db,
            product_id=product_id,
            full_name=full_name,
            phone=phone,
            note=note or None,
        )
    except WebOrderError as exc:
        mapping = {
            "invalid_phone": "شماره موبایل معتبر نیست (مثال: 09121234567).",
            "invalid_name": "نام را کامل وارد کنید.",
            "product_unavailable": "محصول در دسترس نیست.",
        }
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, message=mapping.get(str(exc), "ثبت سفارش ناموفق بود.")),
            status_code=400,
        )

    if settings.OWNER_ID:
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    "🛒 سفارش جدید از وب‌سایت\n\n"
                    f"محصول: {product.title}\n"
                    f"مبلغ: {payment.amount:,} تومان\n"
                    f"هنرجو: {user.full_name}\n"
                    f"موبایل: {user.phone}\n"
                    f"پرداخت #{payment.id} — وضعیت: pending\n"
                    "پس از دریافت رسید در پنل، مانند سایر پرداخت‌ها تأیید کنید."
                ),
            )
        except Exception:
            logger.exception("Failed to notify owner about web order %s", payment.id)

    return templates.TemplateResponse(
        "order_success.html",
        _ctx(
            request,
            product=product,
            payment=payment,
            user=user,
            card=order_service.get_active_card(db),
            bot_buy_link=_bot_link(f"buy_{product.id}"),
            bot_home=_bot_link(),
        ),
    )


@router.get("/classes", response_class=HTMLResponse)
async def classes_list(request: Request, db: Session = Depends(get_db)):
    classes = order_service.list_online_classes(db)
    return templates.TemplateResponse(
        "classes.html",
        _ctx(request, classes=classes),
    )


@router.get("/classes/{course_id}", response_class=HTMLResponse)
async def class_detail(
    request: Request, course_id: int, db: Session = Depends(get_db)
):
    course = order_service.get_online_class(db, course_id)
    if not course:
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, message="کلاس پیدا نشد یا غیرفعال است."),
            status_code=404,
        )
    return templates.TemplateResponse(
        "class_detail.html",
        _ctx(
            request,
            course=course,
            bot_class_link=_bot_link(f"class_{course.id}"),
        ),
    )


@router.post("/classes/{course_id}/inquiry", response_class=HTMLResponse)
async def class_inquiry(
    request: Request,
    course_id: int,
    full_name: str = Form(...),
    phone: str = Form(...),
    message: str = Form(""),
    db: Session = Depends(get_db),
):
    course = order_service.get_online_class(db, course_id)
    if not course:
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, message="کلاس پیدا نشد."),
            status_code=404,
        )

    try:
        user = order_service.ensure_user(db, full_name=full_name, phone=phone)
    except WebOrderError as exc:
        mapping = {
            "invalid_phone": "شماره موبایل معتبر نیست (مثال: 09121234567).",
            "invalid_name": "نام را کامل وارد کنید.",
        }
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, message=mapping.get(str(exc), "ثبت درخواست ناموفق بود.")),
            status_code=400,
        )

    if settings.OWNER_ID:
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    "🎼 درخواست کلاس آنلاین از وب‌سایت\n\n"
                    f"کلاس: {course.name}\n"
                    f"هنرجو: {user.full_name}\n"
                    f"موبایل: {user.phone}\n"
                    f"پیام: {(message or '—')[:500]}\n\n"
                    "ثبت‌نام نهایی از پنل مدیریت کلاس آنلاین انجام شود."
                ),
            )
        except Exception:
            logger.exception("Failed to notify owner about class inquiry")

    return templates.TemplateResponse(
        "inquiry_success.html",
        _ctx(
            request,
            course=course,
            user=user,
            bot_class_link=_bot_link(f"class_{course.id}"),
            bot_home=_bot_link(),
        ),
    )


@router.get("/go-bot")
async def go_bot():
    link = _bot_link()
    if not link:
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url=link, status_code=302)
