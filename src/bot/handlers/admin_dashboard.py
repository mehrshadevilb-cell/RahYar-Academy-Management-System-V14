"""One-screen operational dashboard for the academy owner."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from src.bot.keyboards.admin_menu_keyboard import admin_dashboard_keyboard
from src.core.admin_access import is_admin_user
from src.services.admin_dashboard_service import AdminDashboardService

router = Router()
_dashboard = AdminDashboardService()


@router.callback_query(F.data == "admin_dashboard")
async def admin_dashboard(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    data = _dashboard.summary(db)
    await callback.message.edit_text(
        _dashboard.format_fa(data),
        parse_mode="HTML",
        reply_markup=admin_dashboard_keyboard(),
    )
    await callback.answer()
