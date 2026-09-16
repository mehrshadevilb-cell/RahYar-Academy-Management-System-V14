"""Admin: unified Students panel (Telegram + legacy SpotPlayer imports)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_students_keyboard import (
    student_detail_keyboard,
    students_home_keyboard,
    students_list_keyboard,
)
from src.bot.states.admin_states import AdminState
from src.core.admin_access import is_admin_user
from src.services.admin_log_service import AdminLogService
from src.services.student_admin_service import StudentAdminService, StudentFilter

router = Router()
_svc = StudentAdminService()
_logs = AdminLogService()

_FILTER_MAP = {
    "all": StudentFilter.ALL,
    "tg": StudentFilter.TELEGRAM,
    "legacy": StudentFilter.LEGACY,
}


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_students")
async def admin_students_home(callback: CallbackQuery, state: FSMContext, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    counts = _svc.counts(db)
    text = (
        "👥 <b>هنرجوها</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"کل: <b>{counts['total']}</b>\n"
        f"📱 ثبت‌نام در ربات: <b>{counts['telegram']}</b>\n"
        f"📥 اسپات‌پلیر / قدیم (بدون تلگرام): <b>{counts['legacy']}</b>\n\n"
        "از اینجا می‌توانید همه هنرجوها را ببینید، جستجو کنید و وضعیت را مدیریت کنید."
    )
    await _safe_edit(callback, text, students_home_keyboard(counts))
    await callback.answer()


@router.callback_query(F.data.startswith("stu_list_"))
async def admin_students_list(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    parts = callback.data.split("_")
    # stu_list_{filt}_{page}
    if len(parts) < 4:
        await callback.answer("داده نامعتبر", show_alert=True)
        return
    filt_key = parts[2]
    page = int(parts[3])
    filt = _FILTER_MAP.get(filt_key, StudentFilter.ALL)
    items, total = _svc.list_students(db, filt=filt, page=page)
    title = {
        StudentFilter.ALL: "همه هنرجوها",
        StudentFilter.TELEGRAM: "هنرجوهای تلگرام",
        StudentFilter.LEGACY: "اسپات / قدیم",
    }[filt]
    if not items:
        text = f"👥 <b>{title}</b>\n\nموردی در این صفحه نیست."
    else:
        lines = [f"👥 <b>{title}</b> · صفحه {page + 1} · جمع {total}\n"]
        for item in items:
            lines.append(_svc.format_list_line(item))
            lines.append("────────")
        text = "\n".join(lines)
    await _safe_edit(
        callback,
        text,
        students_list_keyboard(items, filt_key, page, total, _svc.PAGE_SIZE),
    )
    await callback.answer()


@router.callback_query(F.data == "stu_search")
async def admin_students_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminState.waiting_student_phone)
    await callback.message.answer(
        "🔍 نام یا شماره موبایل هنرجو را بفرستید:\n"
        "مثال: <code>0912…</code> یا بخشی از نام",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminState.waiting_student_phone)
async def admin_students_search_result(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    query = (message.text or "").strip()
    if not query or query.startswith("/"):
        await message.answer("❌ یک نام یا شماره معتبر بفرستید.")
        return
    await state.clear()
    items = _svc.search(db, query, limit=12)
    _logs.log(db, message.from_user.id, "STUDENT_SEARCH", f"{query[:80]} → {len(items)}")
    if not items:
        await message.answer("نتیجه‌ای پیدا نشد.")
        return
    lines = [f"🔍 <b>{len(items)} نتیجه</b> برای «{query}»\n"]
    for item in items:
        lines.append(_svc.format_list_line(item))
        lines.append("────────")
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=students_list_keyboard(items, "all", 0, len(items), _svc.PAGE_SIZE),
    )


@router.callback_query(F.data.startswith("stu_view_"))
async def admin_student_view(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    # stu_view_{id}_{filt}_{page}
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("داده نامعتبر", show_alert=True)
        return
    user_id = int(parts[2])
    filt = parts[3]
    page = int(parts[4])
    user = _svc.get_user(db, user_id)
    if not user:
        await callback.answer("هنرجو پیدا نشد", show_alert=True)
        return
    text = _svc.format_detail(db, user)
    await _safe_edit(
        callback,
        text,
        student_detail_keyboard(user_id, filt, page, bool(user.is_active)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stu_toggle_"))
async def admin_student_toggle(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    # stu_toggle_{id}_{0|1}_{filt}_{page}
    parts = callback.data.split("_")
    if len(parts) < 6:
        await callback.answer("داده نامعتبر", show_alert=True)
        return
    user_id = int(parts[2])
    active = parts[3] == "1"
    filt = parts[4]
    page = int(parts[5])
    user = _svc.set_active(db, user_id, active)
    if not user:
        await callback.answer("هنرجو پیدا نشد", show_alert=True)
        return
    _logs.log(
        db,
        callback.from_user.id,
        "STUDENT_TOGGLE",
        f"user={user_id} active={active}",
    )
    text = _svc.format_detail(db, user)
    await _safe_edit(
        callback,
        text,
        student_detail_keyboard(user_id, filt, page, bool(user.is_active)),
    )
    await callback.answer("ذخیره شد ✅")
