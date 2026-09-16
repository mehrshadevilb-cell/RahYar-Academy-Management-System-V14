"""Owner: add/update online enrollments by chatting in Persian."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.states.admin_states import AdminState
from src.core.admin_access import is_admin_user
from src.services.admin_log_service import AdminLogService
from src.services.online_enrollment_chat_parser import parse_enrollment_chat
from src.services.online_enrollment_chat_service import OnlineEnrollmentChatService

router = Router()
_chat = OnlineEnrollmentChatService()
_logs = AdminLogService()


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید و ثبت", callback_data="oe_chat_confirm"),
                InlineKeyboardButton(text="❌ انصراف", callback_data="oe_chat_cancel"),
            ],
            [InlineKeyboardButton(text="✏️ متن جدید", callback_data="admin_online_chat_enroll")],
        ]
    )


@router.callback_query(F.data == "admin_online_chat_enroll")
async def online_chat_enroll_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminState.waiting_online_chat_enroll)
    await state.update_data(oe_chat_draft=None)
    await callback.message.answer(
        "💬 <b>ثبت کلاس با چت</b>\n\n"
        "متن را مثل این مثال‌ها بفرستید:\n\n"
        "• مهدی متاج با شماره 09370745337 هر سه‌شنبه ساعت ۴ تا ۶ "
        "کلاس تنظیم میکس و مسترینگ داره و ۲ جلسه دیگه داره\n\n"
        "• فلانی 0912… ثبت‌نام کرد ۱۲ جلسه برای شنبه‌ها ساعت ۱۰ تا ۱۲ برای ۱۲ هفته\n\n"
        "ربات پیش‌نمایش می‌دهد؛ بعد از تأیید ذخیره می‌شود.\n"
        "/cancel برای خروج",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminState.waiting_online_chat_enroll, F.text == "/cancel")
async def online_chat_cancel_cmd(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user):
        return
    await state.clear()
    await message.answer("لغو شد.")


@router.message(AdminState.waiting_online_chat_enroll)
async def online_chat_receive(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("متن خالی است.")
        return
    draft = parse_enrollment_chat(text)
    course = _chat.match_course(db, draft.course_hint)
    user = None
    if draft.phone:
        user = _chat.profiles.get_profile_by_phone(db, draft.phone)
    preview = _chat.format_preview(draft, course, user)
    await state.update_data(
        oe_chat_raw=text,
        oe_chat_ready=draft.ok and course is not None,
    )
    # Store serializable fields for confirm step
    await state.update_data(
        oe_name=draft.student_name,
        oe_phone=draft.phone,
        oe_course_hint=draft.course_hint,
        oe_sessions=draft.remaining_sessions,
        oe_weeks=draft.weeks,
        oe_plan=draft.plan,
        oe_weekday=draft.weekday,
        oe_t_from=draft.time_from,
        oe_t_to=draft.time_to,
    )
    await message.answer(preview, parse_mode="HTML", reply_markup=_confirm_keyboard())


@router.callback_query(F.data == "oe_chat_cancel")
async def online_chat_cancel_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.clear()
    await callback.message.answer("انصراف داده شد.")
    await callback.answer()


@router.callback_query(F.data == "oe_chat_confirm")
async def online_chat_confirm(callback: CallbackQuery, state: FSMContext, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return
    data = await state.get_data()
    from src.services.online_enrollment_chat_parser import ChatEnrollmentDraft

    draft = ChatEnrollmentDraft(
        student_name=data.get("oe_name"),
        phone=data.get("oe_phone"),
        course_hint=data.get("oe_course_hint"),
        remaining_sessions=data.get("oe_sessions"),
        weeks=data.get("oe_weeks"),
        plan=data.get("oe_plan") or "term",
        weekday=data.get("oe_weekday"),
        time_from=data.get("oe_t_from"),
        time_to=data.get("oe_t_to"),
        raw_text=data.get("oe_chat_raw") or "",
    )
    result = _chat.apply(db, draft)
    await state.clear()
    if result.ok:
        _logs.log(
            db,
            callback.from_user.id,
            "ONLINE_CHAT_ENROLL",
            (result.message or "")[:400],
        )
    await callback.message.answer(result.message)
    await callback.answer("انجام شد" if result.ok else "ناموفق")
