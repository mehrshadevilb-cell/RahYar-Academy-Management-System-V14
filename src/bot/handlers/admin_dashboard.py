"""Owner daily dashboard, inactive students, and system health.

Also handles legacy callback_data «admin_stats» so the old weak stats
screen and the new dashboard are one capability.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from src.core.admin_access import is_admin_user
from src.services.owner_dashboard_service import OwnerDashboardService
from src.services.system_health_service import SystemHealthService

router = Router()
_dashboard = OwnerDashboardService()
_health = SystemHealthService()


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
                    text="😴 هنرجویان غیرفعال",
                    callback_data="admin_inactive_students",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🩺 وضعیت سیستم",
                    callback_data="admin_system_health",
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


def _back_to_dashboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ بازگشت به گزارش امروز", callback_data="admin_dashboard")],
            [InlineKeyboardButton(text="🏠 منوی ادمین", callback_data="admin_home")],
        ]
    )


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data.in_({"admin_dashboard", "admin_stats"}))
async def admin_dashboard(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    summary = _dashboard.get_summary(db)
    await _safe_edit(callback, summary.format_persian(), _dashboard_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_inactive_students")
async def admin_inactive_students(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    rows = _dashboard.list_inactive_enrollments(db, days=14, limit=25)
    text = _dashboard.format_inactive_list(rows, days=14)
    await _safe_edit(callback, text, _back_to_dashboard())
    await callback.answer()


@router.callback_query(F.data == "admin_system_health")
async def admin_system_health(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    report = _health.check()
    await _safe_edit(callback, report.format_persian(), _back_to_dashboard())
    await callback.answer()
