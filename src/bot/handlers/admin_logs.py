from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.states.admin_states import AdminState
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.admin_logs_keyboard import admin_logs_keyboard
from src.services.admin_log_service import AdminLogService
from src.core.config.settings import get_settings


router = Router()

admin_log_service = AdminLogService()

settings = get_settings()

RECENT_LOGS_LIMIT = 20


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


def _format_logs(logs, empty_text: str) -> str:

    if not logs:
        return empty_text

    lines = [
        f"🕐 {log.created_at.strftime('%Y-%m-%d %H:%M')} — {log.description}"
        for log in logs
    ]

    return "\n\n".join(lines)


@router.callback_query(F.data == "admin_logs")
async def admin_logs_view(callback: CallbackQuery, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    logs = admin_log_service.get_recent(db, RECENT_LOGS_LIMIT)

    text = "📜 آخرین اقدامات مدیریتی:\n\n" + _format_logs(
        logs, "هنوز هیچ لاگی ثبت نشده است."
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_logs_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "admin_logs_search")
async def admin_logs_search_start(callback: CallbackQuery, state: FSMContext):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await state.set_state(AdminState.waiting_log_search_keyword)

    await callback.message.answer(
        "کلمه کلیدی مورد نظر برای جستجو در لاگ‌ها را بفرستید "
        "(مثلاً نام دوره، شماره پرداخت، یا نوع اقدام):"
    )

    await callback.answer()


@router.message(AdminState.waiting_log_search_keyword)
async def admin_logs_search_run(message: Message, state: FSMContext, db):

    if not _is_owner(message.from_user.id):
        return

    keyword = (message.text or "").strip()

    await state.clear()

    if not keyword:
        await message.answer(
            "❌ عبارت جستجو نمی‌تواند خالی باشد.",
            reply_markup=admin_back_button("admin_logs"),
        )
        return

    logs = admin_log_service.search(db, keyword, RECENT_LOGS_LIMIT)

    text = f"🔍 نتایج جستجو برای «{keyword}»:\n\n" + _format_logs(
        logs, "چیزی پیدا نشد."
    )

    await message.answer(
        text,
        reply_markup=admin_back_button("admin_logs"),
    )
