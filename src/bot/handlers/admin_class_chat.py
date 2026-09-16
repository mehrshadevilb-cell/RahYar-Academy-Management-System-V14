"""Admin: manage online classes via Persian chat (enroll / absent / present / status)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.states.admin_states import AdminState
from src.core.admin_access import is_admin_user
from src.services.admin_log_service import AdminLogService
from src.services.class_management_chat_service import ClassManagementChatService
from src.services.online_enrollment_chat_parser import ChatEnrollmentDraft
from src.services.online_enrollment_chat_service import OnlineEnrollmentChatService

router = Router()
_mgr = ClassManagementChatService()
_enroll = OnlineEnrollmentChatService()
_logs = AdminLogService()


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید ثبت کلاس", callback_data="class_chat_confirm_enroll"),
                InlineKeyboardButton(text="❌ انصراف", callback_data="class_chat_cancel"),
            ]
        ]
    )


@router.callback_query(F.data == "admin_class_chat")
async def class_chat_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_class_chat)
    await callback.message.answer(_mgr.help_text(), parse_mode="HTML")
    await callback.answer()


@router.message(AdminState.waiting_class_chat, F.text == "/cancel")
async def class_chat_cancel_cmd(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user):
        return
    await state.clear()
    await message.answer("خروج از مدیریت کلاس با چت.")


@router.message(AdminState.waiting_class_chat)
async def class_chat_message(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    text = (message.text or "").strip()
    if not text:
        return
    result = _mgr.handle(db, text)
    if result.needs_confirm and result.draft_payload:
        await state.update_data(class_chat_enroll=result.draft_payload)
        await message.answer(result.message, parse_mode="HTML", reply_markup=_confirm_kb())
        return
    if result.ok and result.intent.value in ("absent", "present"):
        _logs.log(db, message.from_user.id, "CLASS_CHAT_ATTENDANCE", result.message[:400])
    await message.answer(result.message, parse_mode="HTML")


@router.callback_query(F.data == "class_chat_cancel")
async def class_chat_cancel_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        return
    await state.update_data(class_chat_enroll=None)
    await callback.message.answer("انصراف از ثبت کلاس.")
    await callback.answer()


@router.callback_query(F.data == "class_chat_confirm_enroll")
async def class_chat_confirm_enroll(callback: CallbackQuery, state: FSMContext, db):
    if not is_admin_user(callback.from_user):
        return
    data = await state.get_data()
    payload = data.get("class_chat_enroll") or {}
    draft = ChatEnrollmentDraft(
        student_name=payload.get("name"),
        phone=payload.get("phone"),
        course_hint=payload.get("course_hint"),
        remaining_sessions=payload.get("sessions"),
        weeks=payload.get("weeks"),
        plan=payload.get("plan") or "term",
        weekday=payload.get("weekday"),
        time_from=payload.get("t_from"),
        time_to=payload.get("t_to"),
        raw_text=payload.get("raw") or "",
    )
    applied = _enroll.apply(db, draft)
    await state.update_data(class_chat_enroll=None)
    if applied.ok:
        _logs.log(db, callback.from_user.id, "CLASS_CHAT_ENROLL", applied.message[:400])
    await callback.message.answer(applied.message)
    await callback.answer()
