from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.states.support_states import SupportState
from src.core.config.settings import get_settings
from src.services.profile_service import ProfileService
from src.services.support_service import (
    MAX_MESSAGE_LENGTH,
    MAX_OPEN_PER_USER,
    SupportService,
    SupportServiceError,
)
from src.database.models.support_request import SupportStatus

router = Router()
profile_service = ProfileService()
support_service = SupportService()
settings = get_settings()


@router.message(F.text == "🆘 پشتیبانی")
async def support_menu(message: Message, state: FSMContext, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    recent = support_service.get_by_user(db, user.id, limit=5)
    lines = [
        "🆘 پشتیبانی راه‌یار\n",
        "پیام خود را بنویسید تا برای مدیریت ارسال شود.\n",
        f"حداکثر {MAX_OPEN_PER_USER} تیکت باز همزمان مجاز است.\n",
    ]
    if recent:
        lines.append("آخرین درخواست‌های شما:")
        status_map = {
            SupportStatus.OPEN: "⏳ باز",
            SupportStatus.ANSWERED: "💬 پاسخ‌داده‌شده",
            SupportStatus.CLOSED: "✅ بسته‌شده",
        }
        for item in recent:
            label = status_map.get(item.status, str(item.status))
            lines.append(f"• #{item.id} — {label}")
            if item.admin_reply:
                lines.append(f"  پاسخ: {item.admin_reply[:120]}")

    await state.set_state(SupportState.waiting_message)
    await message.answer("\n".join(lines))


@router.message(SupportState.waiting_message)
async def support_submit(message: Message, state: FSMContext, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await state.clear()
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    text = (message.text or "").strip()
    if text in {"/cancel", "انصراف"}:
        await state.clear()
        await message.answer("✅ ارسال پیام پشتیبانی لغو شد.")
        return

    try:
        request = support_service.create_request(
            db,
            user_id=user.id,
            telegram_id=str(message.from_user.id),
            message=text,
        )
    except SupportServiceError as exc:
        code = str(exc)
        if code == "empty_message":
            await message.answer("❌ پیام خالی است. متن مشکل را بنویسید یا «انصراف» بفرستید.")
            return
        if code == "message_too_long":
            await message.answer(
                f"❌ پیام نباید بیشتر از {MAX_MESSAGE_LENGTH} کاراکتر باشد."
            )
            return
        if code == "too_many_open":
            await state.clear()
            await message.answer(
                f"❌ شما هم‌اکنون {MAX_OPEN_PER_USER} تیکت باز دارید. "
                "منتظر پاسخ مدیریت بمانید."
            )
            return
        await state.clear()
        await message.answer("❌ ثبت درخواست با خطا مواجه شد.")
        return

    await state.clear()
    await message.answer(
        f"✅ درخواست پشتیبانی #{request.id} ثبت شد.\n"
        "به محض پاسخ، همین‌جا به شما اطلاع می‌دهیم."
    )

    if settings.OWNER_ID:
        try:
            name = user.full_name or "بدون نام"
            await message.bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    f"🆘 تیکت پشتیبانی جدید #{request.id}\n"
                    f"کاربر: {name} ({message.from_user.id})\n\n"
                    f"{request.message[:1500]}"
                ),
            )
        except Exception:
            pass
