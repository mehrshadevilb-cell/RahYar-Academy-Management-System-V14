"""Admin: SpotPlayer test-license panel (API test=true, no paid quota)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.core.admin_access import is_admin_user
from src.core.config.settings import get_settings
from src.database.models.course import Course, ProductDeliveryType
from src.database.models.user import User
from src.services.admin_log_service import AdminLogService
from src.services.license_service import LicenseService
from src.services.profile_service import ProfileService

router = Router()
_license = LicenseService()
_profile = ProfileService()
_logs = AdminLogService()


def _panel_keyboard(products: list[Course]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for product in products[:12]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🧪 تست · {product.title[:28]}",
                    callback_data=f"sp_test_issue_{product.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="admin_spotplayer_test")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _status_text(products: list[Course]) -> str:
    settings = get_settings()
    key_ok = bool((settings.SPOTPLAYER_API_KEY or "").strip())
    mode = "🧪 TEST (بدون هزینه)" if settings.SPOTPLAYER_TEST_MODE else "💳 PRODUCTION (لایسنس واقعی)"
    lines = [
        "🔌 <b>تست SpotPlayer</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"API Key: {'✅ تنظیم شده' if key_ok else '❌ تنظیم نشده'}",
        f"حالت پیش‌فرض صدور: <b>{mode}</b>",
        "",
        "دکمهٔ زیر همیشه با <code>test=true</code> لایسنس می‌سازد",
        "(طبق مستندات SpotPlayer هزینه/سهمیهٔ واقعی مصرف نمی‌شود).",
        "",
        "لایسنس تست برای <b>حساب تلگرام خودتان</b> ثبت می‌شود.",
        "━━━━━━━━━━━━━━━━━━",
    ]
    if not products:
        lines.append("⚠️ هیچ محصول SpotPlayer فعالی پیدا نشد.")
    else:
        lines.append(f"محصولات قابل تست: <b>{len(products)}</b>")
    return "\n".join(lines)


def _spotplayer_products(db) -> list[Course]:
    rows = (
        db.query(Course)
        .filter(Course.is_active.is_(True))
        .order_by(Course.sort_order, Course.id)
        .all()
    )
    out: list[Course] = []
    for course in rows:
        delivery = course.delivery_type
        value = delivery.value if hasattr(delivery, "value") else str(delivery)
        if value != ProductDeliveryType.SPOTPLAYER.value and value != "spotplayer":
            # Still allow if product has enabled SpotPlayer course ids.
            pass
        enabled = [sp for sp in (course.spotplayer_courses or []) if sp.enabled]
        if enabled:
            out.append(course)
    return out


@router.callback_query(F.data == "admin_spotplayer_test")
async def admin_spotplayer_test_home(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    products = _spotplayer_products(db)
    text = _status_text(products)
    try:
        await callback.message.edit_text(text, reply_markup=_panel_keyboard(products), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=_panel_keyboard(products), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sp_test_issue_"))
async def admin_spotplayer_test_issue(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    product_id = int(callback.data.replace("sp_test_issue_", ""))
    product = db.query(Course).filter(Course.id == product_id).first()
    if not product:
        await callback.answer("محصول پیدا نشد", show_alert=True)
        return

    user = _profile.get_profile(db, str(callback.from_user.id))
    if not user:
        await callback.answer("اول /start بزنید تا پروفایل ادمین ساخته شود.", show_alert=True)
        return

    await callback.answer("در حال ساخت لایسنس تست…")
    license_row = await _license.issue_test_license(
        db=db,
        user_id=user.id,
        user_full_name=user.full_name or "Admin Test",
        user_phone=user.phone,
        product=product,
    )

    _logs.log(
        db,
        callback.from_user.id,
        "SPOTPLAYER_TEST_LICENSE",
        f"test license product={product.title} status={license_row.status} id={license_row.spotplayer_license_id}",
    )

    if license_row.status == "active":
        key_preview = (license_row.license_key or "")[:40]
        text = (
            f"✅ <b>لایسنس تست ساخته شد</b>\n"
            f"محصول: {product.title}\n"
            f"SpotPlayer id: <code>{license_row.spotplayer_license_id}</code>\n"
            f"Key: <code>{key_preview}…</code>\n"
            f"flag: {license_row.error_message or 'TEST'}\n\n"
            "این لایسنس با <code>test=true</code> ساخته شده و برای تست API است."
        )
    else:
        text = (
            f"❌ ساخت لایسنس تست ناموفق\n"
            f"محصول: {product.title}\n"
            f"خطا: {license_row.error_message or 'نامشخص'}"
        )

    products = _spotplayer_products(db)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=_panel_keyboard(products))
