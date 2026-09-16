"""Owner daily dashboard — thin Telegram layer over OwnerDashboardService."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.core.admin_access import is_admin_user
from src.services.owner_dashboard_service import OwnerDashboardService

router = Router()
_dashboard = OwnerDashboardService()


def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 پرداخت‌های در انتظار",
                    callback_data="admin_pending",
                ),
                InlineKeyboardButton(
                    text="📅 رزروهای در انتظار",
                    callback_data="admin_reservations",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 اقساط",
                    callback_data="admin_installments",
                ),
                InlineKeyboardButton(
                    text="📊 خروجی CSV",
                    callback_data="admin_reports",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 بروزرسانی",
                    callback_data="admin_dashboard",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ بازگشت",
                    callback_data="admin_home",
                ),
            ],
        ]
    )


@router.callback_query(F.data == "admin_dashboard")
async def admin_dashboard(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    summary = _dashboard.get_summary(db)
    text = summary.format_persian()

    try:
        await callback.message.edit_text(text, reply_markup=_dashboard_keyboard())
    except Exception:
        # e.g. message content unchanged on refresh
        await callback.message.answer(text, reply_markup=_dashboard_keyboard())

    await callback.answer()
