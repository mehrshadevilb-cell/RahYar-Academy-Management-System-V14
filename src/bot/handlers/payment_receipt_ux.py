"""Receipt-waiting UX handlers for card-to-card payments.

Register this router next to the main payment router so cancel / confirm
callbacks and non-media guidance work while PaymentState.waiting_receipt
is active. The payment instructions message should attach
receipt_waiting_keyboard() when entering that state.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.main_menu import get_main_menu
from src.bot.keyboards.payment_keyboard import receipt_waiting_keyboard
from src.bot.states.payment_states import PaymentState
from src.services.profile_service import ProfileService

router = Router()
profile_service = ProfileService()


@router.callback_query(F.data == "pay_cancel")
async def cancel_payment_flow(callback: CallbackQuery, state: FSMContext, db):
    current = await state.get_state()
    if current not in {PaymentState.waiting_receipt, PaymentState.waiting_discount_code}:
        await callback.answer("خرید فعالی وجود ندارد.", show_alert=True)
        return

    await state.clear()
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    role = getattr(user, "role", None) if user else None
    await callback.message.answer(
        "❌ خرید لغو شد.\nهر زمان خواستید می‌توانید دوباره از منوی دوره‌ها اقدام کنید.",
        reply_markup=get_main_menu(role),
    )
    await callback.answer("لغو شد")


@router.callback_query(F.data == "pay_confirm_paid")
async def confirm_paid_reminder(callback: CallbackQuery, state: FSMContext):
    if await state.get_state() != PaymentState.waiting_receipt:
        await callback.answer("در مرحله ارسال رسید نیستید.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "✅ عالی.\nحالا لطفاً <b>عکس یا فایل رسید پرداخت</b> را همین‌جا ارسال کنید.\n"
        "بدون رسید، پرداخت برای ادمین قابل بررسی نیست.",
        parse_mode="HTML",
        reply_markup=receipt_waiting_keyboard(),
    )


@router.message(PaymentState.waiting_receipt)
async def waiting_receipt_non_media(message: Message, state: FSMContext):
    await message.answer(
        "⚠️ برای تکمیل خرید باید <b>عکس یا فایل رسید</b> را ارسال کنید.\n"
        "متن به‌تنهایی کافی نیست.\n\nاگر منصرف شدید، روی «انصراف» بزنید.",
        parse_mode="HTML",
        reply_markup=receipt_waiting_keyboard(),
    )
