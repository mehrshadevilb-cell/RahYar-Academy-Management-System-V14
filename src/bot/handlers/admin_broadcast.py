import asyncio

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot.states.admin_states import AdminState
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.admin_broadcast_keyboard import broadcast_confirm_keyboard
from src.services.broadcast_service import BroadcastService
from src.services.admin_log_service import AdminLogService
from src.core.constants import admin_actions
from src.core.config.settings import get_settings


router = Router()

broadcast_service = BroadcastService()
admin_log_service = AdminLogService()

settings = get_settings()


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await state.set_state(AdminState.waiting_broadcast_content)

    await callback.message.answer(
        "📢 پیامی که می‌خواهید برای همه هنرجویان ارسال شود را بفرستید "
        "(متن، عکس، ویدیو یا صوت).\n\n"
        "برای انصراف /cancel را بفرستید."
    )

    await callback.answer()


@router.message(AdminState.waiting_broadcast_content, F.text == "/cancel")
async def admin_broadcast_cancel_input(message: Message, state: FSMContext):

    if not _is_owner(message.from_user.id):
        return

    await state.clear()

    await message.answer("لغو شد.", reply_markup=admin_back_button())


@router.message(AdminState.waiting_broadcast_content)
async def admin_broadcast_receive_content(message: Message, state: FSMContext, db):

    if not _is_owner(message.from_user.id):
        return

    audience = broadcast_service.get_audience(db)
    audience_count = len(
        [a for a in audience if a.telegram_id != str(message.from_user.id)]
    )

    await state.update_data(
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    await state.set_state(AdminState.waiting_broadcast_confirm)

    await message.answer("👆 این پیامی است که ارسال خواهد شد:")
    await message.copy_to(chat_id=message.chat.id)

    if audience_count == 0:
        await message.answer(
            "⚠️ در حال حاضر هیچ کاربری با اکانت تلگرام متصل ثبت نشده است.",
            reply_markup=admin_back_button(),
        )
        await state.clear()
        return

    await message.answer(
        f"این پیام برای {audience_count:,} هنرجو ارسال می‌شود. تایید می‌کنید؟",
        reply_markup=broadcast_confirm_keyboard(audience_count),
    )


@router.callback_query(F.data == "admin_broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text("❌ ارسال پیام همگانی لغو شد.")
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast_confirm")
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    data = await state.get_data()
    from_chat_id = data.get("from_chat_id")
    message_id = data.get("message_id")

    await state.clear()

    if not from_chat_id or not message_id:
        await callback.answer("این درخواست منقضی شده. دوباره تلاش کنید.", show_alert=True)
        return

    await callback.message.edit_text("📤 در حال ارسال... 0%")
    await callback.answer()

    progress_message = callback.message

    async def on_progress(sent_so_far: int, total: int):
        percent = int(sent_so_far / total * 100) if total else 100
        try:
            await progress_message.edit_text(f"📤 در حال ارسال... {percent}%")
        except Exception:
            # Ignore "message not modified" / transient edit races - the
            # final summary message is the source of truth either way.
            pass

    result = await broadcast_service.send(
        bot=bot,
        db=db,
        from_chat_id=from_chat_id,
        message_id=message_id,
        exclude_telegram_ids={str(callback.from_user.id)},
        on_progress=on_progress,
    )

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.BROADCAST_SENT,
        f"پیام همگانی ارسال شد (موفق: {result.sent}, مسدود: {result.blocked}, خطا: {result.failed})",
    )

    await callback.message.answer(
        "✅ ارسال پیام همگانی تمام شد.\n\n"
        f"👥 مجموع مخاطبان: {result.total:,}\n"
        f"✅ ارسال موفق: {result.sent:,}\n"
        f"🚫 مسدود/غیرفعال: {result.blocked:,}\n"
        f"⚠️ خطا: {result.failed:,}",
        reply_markup=admin_back_button(),
    )
