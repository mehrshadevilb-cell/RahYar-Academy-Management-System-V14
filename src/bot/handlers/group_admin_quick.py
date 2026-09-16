""" /admin_quick — compact ops summary for any full admin, usable in groups."""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from src.core.admin_access import require_admin
from src.services.admin_dashboard_service import AdminDashboardService

router = Router()
_dashboard = AdminDashboardService()


@router.message(Command("admin_quick"))
async def admin_quick(message: Message, db):
    if not message.from_user or not require_admin(message.from_user):
        # Silent ignore in groups so non-admins are not spammed with denial.
        if message.chat and message.chat.type == ChatType.PRIVATE:
            await message.answer("⛔️ دسترسی ادمین ندارید.")
        return

    data = _dashboard.summary(db)
    text = _dashboard.format_fa(data)
    text += (
        "\n\n<i>دسترسی کامل ادمین — همان قابلیت‌های پنل اصلی.\n"
        "جزئیات بیشتر از منوی «🛠 پنل مدیریت» در چت خصوصی.</i>"
    )
    await message.answer(text, parse_mode="HTML")
