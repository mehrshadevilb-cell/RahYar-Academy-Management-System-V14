""" /admin_quick — compact ops summary for any full admin, usable in groups."""

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from src.core.admin_access import require_admin
from src.services.owner_dashboard_service import OwnerDashboardService

router = Router()
_dashboard = OwnerDashboardService()


@router.message(Command("admin_quick"))
async def admin_quick(message: Message, db):
    if not message.from_user or not require_admin(message.from_user):
        # Silent ignore in groups so non-admins are not spammed with denial.
        if message.chat and message.chat.type == ChatType.PRIVATE:
            await message.answer("⛔️ دسترسی ادمین ندارید.")
        return

    summary = _dashboard.get_summary(db)
    text = summary.format_persian()
    text += (
        "\n\n✅ دسترسی کامل ادمین — همان قابلیت‌های پنل اصلی.\n"
        "جزئیات بیشتر: چت خصوصی → «🛠 پنل مدیریت»"
    )
    await message.answer(text)
