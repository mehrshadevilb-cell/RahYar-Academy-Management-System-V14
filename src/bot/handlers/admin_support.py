from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.support_keyboard import (
    support_open_list_keyboard,
    support_ticket_keyboard,
)
from src.bot.states.support_states import AdminSupportState
from src.core.config.settings import get_settings
from src.core.constants import admin_actions
from src.services.admin_log_service import AdminLogService
from src.services.profile_service import ProfileService
from src.services.support_service import SupportService, SupportServiceError

router = Router()
settings = get_settings()
support_service = SupportService()
admin_log_service = AdminLogService()
profile_service = ProfileService()


def _is_owner(user_id: int) -> bool:
    return bool(settings.OWNER_ID) and user_id == settings.OWNER_ID


@router.callback_query(F.data == "admin_support")
async def admin_support_list(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return

    open_tickets = support_service.get_open(db)
    if not open_tickets:
        await callback.message.edit_text(
            "✅ هیچ تیکت پشتیبانی بازی وجود ندارد.",
            reply_markup=admin_back_button(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"🆘 تیکت‌های باز ({len(open_tickets)}):\nیکی را انتخاب کنید:",
        reply_markup=support_open_list_keyboard(open_tickets),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support_view_"))
async def admin_support_view(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return

    request_id = int(callback.data.replace("support_view_", ""))
    request = support_service.get_by_id(db, request_id)
    if not request:
        await callback.answer("تیکت پیدا نشد", show_alert=True)
        return

    user = profile_service.get_profile_by_id(db, request.user_id)
    name = user.full_name if user else "—"

    await callback.message.edit_text(
        f"🆘 تیکت #{request.id}\n"
        f"وضعیت: {request.status.value}\n"
        f"کاربر: {name} ({request.telegram_id})\n"
        f"زمان: {request.created_at}\n\n"
        f"{request.message}\n\n"
        f"پاسخ فعلی: {request.admin_reply or '—'}",
        reply_markup=support_ticket_keyboard(request),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support_reply_"))
async def admin_support_reply_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return

    request_id = int(callback.data.replace("support_reply_", ""))
    await state.set_state(AdminSupportState.waiting_reply)
    await state.update_data(support_request_id=request_id)
    await callback.message.answer(
        f"پاسخ تیکت #{request_id} را بنویسید (یا «انصراف»):"
    )
    await callback.answer()


@router.message(AdminSupportState.waiting_reply)
async def admin_support_reply_submit(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return

    text = (message.text or "").strip()
    if text in {"/cancel", "انصراف"}:
        await state.clear()
        await message.answer("✅ پاسخ لغو شد.", reply_markup=admin_back_button("admin_support"))
        return

    data = await state.get_data()
    request_id = data.get("support_request_id")
    await state.clear()

    try:
        request = support_service.reply(db, request_id, text)
    except SupportServiceError as exc:
        code = str(exc)
        mapping = {
            "not_found": "❌ تیکت پیدا نشد.",
            "already_closed": "❌ این تیکت قبلاً بسته شده است.",
            "empty_reply": "❌ پاسخ خالی است.",
            "reply_too_long": "❌ پاسخ خیلی طولانی است.",
        }
        await message.answer(mapping.get(code, "❌ خطا در ثبت پاسخ."))
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.SUPPORT_REPLY,
        f"پاسخ به تیکت پشتیبانی #{request.id}",
    )

    await message.answer(
        f"✅ پاسخ تیکت #{request.id} ثبت شد.",
        reply_markup=admin_back_button("admin_support"),
    )

    try:
        await message.bot.send_message(
            chat_id=int(request.telegram_id),
            text=(
                f"💬 پاسخ پشتیبانی به تیکت #{request.id}:\n\n"
                f"{request.admin_reply}\n\n"
                f"درخواست شما:\n{request.message[:500]}"
            ),
        )
    except Exception:
        await message.answer("⚠️ پاسخ ذخیره شد ولی ارسال به کاربر ناموفق بود.")


@router.callback_query(F.data.startswith("support_close_"))
async def admin_support_close(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return

    request_id = int(callback.data.replace("support_close_", ""))
    try:
        request = support_service.close(db, request_id)
    except SupportServiceError as exc:
        code = str(exc)
        if code == "already_closed":
            await callback.answer("قبلاً بسته شده", show_alert=True)
            return
        await callback.answer("خطا", show_alert=True)
        return

    admin_log_service.log(
        db,
        callback.from_user.id,
        admin_actions.SUPPORT_CLOSE,
        f"بستن تیکت پشتیبانی #{request.id}",
    )

    await callback.message.edit_text(
        f"✅ تیکت #{request.id} بسته شد.",
        reply_markup=admin_back_button("admin_support"),
    )
    await callback.answer()

    try:
        await callback.bot.send_message(
            chat_id=int(request.telegram_id),
            text=f"✅ تیکت پشتیبانی #{request.id} توسط مدیریت بسته شد.",
        )
    except Exception:
        pass
