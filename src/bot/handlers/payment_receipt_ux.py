"""Card-to-card receipt waiting UX: cancel, confirm reminder, non-media guidance.

Registered after the main payment router so photo/document receipt handlers win.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.main_menu import get_main_menu
from src.bot.keyboards.payment_keyboard import receipt_waiting_keyboard
from src.bot.states.payment_states import PaymentState
from src.database.models.user import UserRole
from src.services.profile_service import ProfileService

router = Router()
_profile = ProfileService()


@router.callback_query(F.data == "pay_cancel", PaymentState.waiting_receipt)
async def pay_cancel(callback: CallbackQuery, state: FSMContext, db):
    await state.clear()
    role = UserRole.STUDENT
    user = _profile.get_profile(db, str(callback.from_user.id))
    if user:
        role = user.role
    await callback.message.answer(
        "❌ خرید لغو شد. هر زمان آماده بودید دوباره از «📚 دوره ها» اقدام کنید.",
        reply_markup=get_main_menu(role),
    )
    await callback.answer("انصراف انجام شد")


@router.callback_query(F.data == "pay_confirm_paid", PaymentState.waiting_receipt)
async def pay_confirm_paid(callback: CallbackQuery):
    await callback.message.answer(
        "📸 لطفاً <b>عکس یا فایل رسید</b> کارت‌به‌کارت را همین‌جا ارسال کنید.\n"
        "تا وقتی رسید را نفرستید، پرداخت ثبت نمی‌شود.",
        parse_mode="HTML",
        reply_markup=receipt_waiting_keyboard(),
    )
    await callback.answer()


@router.message(PaymentState.waiting_receipt, F.text)
async def waiting_receipt_text_guidance(message: Message):
    await message.answer(
        "⚠️ در این مرحله فقط <b>عکس یا فایل رسید</b> پذیرفته می‌شود.\n"
        "متن به‌جای رسید قابل قبول نیست.\n\n"
        "اگر پرداخت را انجام داده‌اید، رسید را بفرستید؛ در غیر این صورت «انصراف» را بزنید.",
        parse_mode="HTML",
        reply_markup=receipt_waiting_keyboard(),
    )
