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


def _render(
    request: Request,
    name: str,
    *,
    status_code: int = 200,
    **extra,
) -> HTMLResponse:
    """Starlette 0.37+ expects TemplateResponse(request, name, context)."""
    return templates.TemplateResponse(
        request,
        name,
        _ctx(request, **extra),
        status_code=status_code,
    )


def _safe_list_products(db: Session):
    try:
        return order_service.list_products(db)[:6]
    except Exception:
        logger.exception("Failed to list products for storefront home")
        return []


def _safe_list_classes(db: Session):
    try:
        return order_service.list_online_classes(db)[:6]
    except Exception:
        logger.exception("Failed to list online classes for storefront home")
        return []


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    try:
        products = _safe_list_products(db)
        classes = _safe_list_classes(db)
        return _render(request, "home.html", products=products, classes=classes)
    except Exception:
        logger.exception("Storefront home failed; serving minimal fallback")
        bot_link = _bot_link() or "#"
        html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"/><title>{settings.SITE_NAME}</title>
<style>body{{font-family:Tahoma,sans-serif;background:#0f1419;color:#f2f5f8;padding:2rem;line-height:1.8}}
a{{color:#3d9cf0}}</style></head>
<body>
<h1>{settings.SITE_NAME}</h1>
<p>{settings.SITE_TAGLINE}</p>
<p><a href="/products">دوره‌ها</a> · <a href="/classes">کلاس آنلاین</a>
· <a href="{bot_link}" target="_blank" rel="noopener">ربات تلگرام</a></p>
<p style="color:#9aa8b8">فهرست موقتاً در دسترس نیست؛ از ربات استفاده کنید.</p>
</body></html>"""
        return HTMLResponse(content=html, status_code=200)


@router.get("/products", response_class=HTMLResponse)
async def products_list(request: Request, db: Session = Depends(get_db)):
    try:
        products = order_service.list_products(db)
    except Exception:
        logger.exception("Failed to list products")
        products = []
    try:
        return _render(request, "products.html", products=products)
    except Exception:
        logger.exception("products template failed")
        return HTMLResponse(
            "<html dir=rtl><body><h1>دوره‌ها</h1><p>موقتاً در دسترس نیست.</p>"
            "<p><a href=/>خانه</a></p></body></html>",
            status_code=200,
        )


@router.get("/products/{product_id}", response_class=HTMLResponse)
async def product_detail(
    request: Request, product_id: int, db: Session = Depends(get_db)
):
    product = order_service.get_product(db, product_id)
    if not product:
        return _render(
            request,
            "error.html",
            status_code=404,
            message="محصول پیدا نشد یا غیرفعال است.",
        )
    card = order_service.get_active_card(db)
    return _render(
        request,
        "product_detail.html",
        product=product,
        card=card,
        bot_buy_link=_bot_link(f"buy_{product.id}"),
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
        return _render(
            request,
            "error.html",
            status_code=400,
            message=mapping.get(str(exc), "ثبت سفارش ناموفق بود."),
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

    return _render(
        request,
        "order_success.html",
        product=product,
        payment=payment,
        user=user,
        card=order_service.get_active_card(db),
        bot_buy_link=_bot_link(f"buy_{product.id}"),
        bot_home=_bot_link(),
    )


@router.get("/classes", response_class=HTMLResponse)
async def classes_list(request: Request, db: Session = Depends(get_db)):
    try:
        classes = order_service.list_online_classes(db)
    except Exception:
        logger.exception("Failed to list classes")
        classes = []
    try:
        return _render(request, "classes.html", classes=classes)
    except Exception:
        logger.exception("classes template failed")
        return HTMLResponse(
            "<html dir=rtl><body><h1>کلاس آنلاین</h1><p>موقتاً در دسترس نیست.</p>"
            "<p><a href=/>خانه</a></p></body></html>",
            status_code=200,
        )


@router.get("/classes/{course_id}", response_class=HTMLResponse)
async def class_detail(
    request: Request, course_id: int, db: Session = Depends(get_db)
):
    course = order_service.get_online_class(db, course_id)
    if not course:
        return _render(
            request,
            "error.html",
            status_code=404,
            message="کلاس پیدا نشد یا غیرفعال است.",
        )
    return _render(
        request,
        "class_detail.html",
        course=course,
        bot_class_link=_bot_link(f"class_{course.id}"),
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
        return _render(
            request,
            "error.html",
            status_code=404,
            message="کلاس پیدا نشد.",
        )

    try:
        user = order_service.ensure_user(db, full_name=full_name, phone=phone)
    except WebOrderError as exc:
        mapping = {
            "invalid_phone": "شماره موبایل معتبر نیست (مثال: 09121234567).",
            "invalid_name": "نام را کامل وارد کنید.",
        }
        return _render(
            request,
            "error.html",
            status_code=400,
            message=mapping.get(str(exc), "ثبت درخواست ناموفق بود."),
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

    return _render(
        request,
        "inquiry_success.html",
        course=course,
        user=user,
        bot_class_link=_bot_link(f"class_{course.id}"),
        bot_home=_bot_link(),
    )


@router.get("/go-bot")
async def go_bot():
    link = _bot_link()
    if not link:
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url=link, status_code=302)
