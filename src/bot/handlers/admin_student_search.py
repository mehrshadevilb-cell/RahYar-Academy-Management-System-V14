"""Admin: search students by phone or name."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.states.admin_states import AdminState
from src.core.admin_access import is_admin_user
from src.services.admin_log_service import AdminLogService
from src.services.student_lookup_service import StudentLookupService

router = Router()
_lookup = StudentLookupService()
_logs = AdminLogService()


@router.callback_query(F.data == "admin_student_search")
async def admin_student_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminState.waiting_student_phone)
    await callback.message.answer(
        "🔍 نام یا شماره موبایل هنرجو را بفرستید:\n"
        "مثال: <code>0912…</code> یا بخشی از نام",
        parse_mode="HTML",
        reply_markup=admin_back_button("admin_home"),
    )
    await callback.answer()


@router.message(AdminState.waiting_student_phone)
async def admin_student_search_result(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    query = (message.text or "").strip()
    if not query or query.startswith("/"):
        await message.answer("❌ یک نام یا شماره معتبر بفرستید.")
        return

    users = _lookup.search(db, query, limit=12)
    await state.clear()
    _logs.log(
        db,
        message.from_user.id,
        "STUDENT_SEARCH",
        f"جستجوی هنرجو: {query[:80]} → {len(users)} نتیجه",
    )

    if not users:
        await message.answer(
            "نتیجه‌ای پیدا نشد.",
            reply_markup=admin_back_button("admin_home"),
        )
        return

    chunks = [f"🔍 <b>{len(users)} نتیجه</b> برای «{query}»:\n"]
    for user in users:
        chunks.append(_lookup.format_user_card(db, user))
    text = "\n\n────────\n\n".join(chunks)
    if len(text) > 3900:
        text = text[:3900] + "\n…"
    await message.answer(text, parse_mode="HTML", reply_markup=admin_back_button("admin_home"))
