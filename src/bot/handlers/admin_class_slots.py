import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.class_slot_keyboard import (
    admin_slot_list_keyboard,
    admin_slots_home_keyboard,
)
from src.bot.states.class_slot_states import AdminClassSlotState
from src.core.config.settings import get_settings
from src.core.constants import admin_actions
from src.services.admin_log_service import AdminLogService
from src.services.class_slot_service import ClassSlotService, ClassSlotServiceError
from src.services.online_course_service import OnlineCourseService

router = Router()
settings = get_settings()
slot_service = ClassSlotService()
online_course_service = OnlineCourseService()
admin_log_service = AdminLogService()

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _is_owner(user_id: int) -> bool:
    return bool(settings.OWNER_ID) and user_id == settings.OWNER_ID


@router.callback_query(F.data == "admin_slots")
async def admin_slots_home(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.message.edit_text(
        "🗓 زمان‌های آزادی که هنرجو می‌تواند از آن‌ها رزرو کند:",
        reply_markup=admin_slots_home_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_slot_list")
async def admin_slot_list(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    slots = slot_service.list_for_admin(db)
    if not slots:
        await callback.message.edit_text(
            "هنوز زمانی ثبت نشده.",
            reply_markup=admin_back_button("admin_slots"),
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        "برای بستن یک زمان روی آن بزنید:\n"
        + "\n".join(
            f"#{s.id} کلاس {s.online_course_id} | {s.slot_date} {s.slot_time} "
            f"({s.booked_count}/{s.capacity})"
            for s in slots[:20]
        ),
        reply_markup=admin_slot_list_keyboard(slots),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_slot_close_"))
async def admin_slot_close(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    slot_id = int(callback.data.replace("admin_slot_close_", ""))
    try:
        slot = slot_service.close(db, slot_id)
    except ClassSlotServiceError:
        await callback.answer("پیدا نشد", show_alert=True)
        return
    admin_log_service.log(
        db,
        callback.from_user.id,
        admin_actions.CLASS_SLOT_CLOSE,
        f"زمان آزاد #{slot.id} ({slot.slot_date} {slot.slot_time}) بسته شد",
    )
    await callback.answer("بسته شد")
    await admin_slot_list(callback, db)


@router.callback_query(F.data == "admin_slot_add")
async def admin_slot_add_start(callback: CallbackQuery, state: FSMContext, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    courses = online_course_service.get_active_courses(db)
    if not courses:
        await callback.message.answer("ابتدا یک کلاس آنلاین فعال بسازید.")
        await callback.answer()
        return
    lines = ["شناسه کلاس را بفرستید:"]
    for c in courses:
        lines.append(f"• {c.id}: {c.name}")
    await state.set_state(AdminClassSlotState.waiting_course_id)
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.message(AdminClassSlotState.waiting_course_id)
async def admin_slot_course(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("فقط عدد شناسه را بفرستید:")
        return
    course = online_course_service.get_course_by_id(db, int(raw))
    if not course or not course.is_active:
        await message.answer("کلاس پیدا نشد. دوباره:")
        return
    await state.update_data(online_course_id=course.id)
    await state.set_state(AdminClassSlotState.waiting_date)
    await message.answer(
        f"تاریخ جلالی برای «{course.name}» (مثال 1404-07-20):"
    )


@router.message(AdminClassSlotState.waiting_date)
async def admin_slot_date(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    slot_date = (message.text or "").strip()
    if len(slot_date) < 8:
        await message.answer("تاریخ نامعتبر است. مثال: 1404-07-20")
        return
    await state.update_data(slot_date=slot_date)
    await state.set_state(AdminClassSlotState.waiting_time)
    await message.answer("ساعت را بفرستید (مثال 18:30):")


@router.message(AdminClassSlotState.waiting_time)
async def admin_slot_time(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    slot_time = (message.text or "").strip()
    if not TIME_PATTERN.match(slot_time):
        await message.answer("فرمت ساعت نادرست است. مثال: 18:30")
        return
    data = await state.get_data()
    await state.clear()
    try:
        slot = slot_service.create_slot(
            db,
            online_course_id=data["online_course_id"],
            slot_date=data["slot_date"],
            slot_time=slot_time,
        )
    except ClassSlotServiceError as exc:
        await message.answer(f"❌ ثبت زمان ناموفق: {exc}")
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.CLASS_SLOT_CREATE,
        f"زمان آزاد #{slot.id}: {slot.slot_date} {slot.slot_time} کلاس {slot.online_course_id}",
    )
    await message.answer(
        f"✅ زمان #{slot.id} ثبت شد:\n{slot.slot_date} — {slot.slot_time}",
        reply_markup=admin_back_button("admin_slots"),
    )
