import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.class_slot_keyboard import (
    admin_slots_list_keyboard,
    admin_slot_detail_keyboard,
    admin_slot_courses_keyboard,
)
from src.bot.states.admin_states import AdminState
from src.core.config.settings import get_settings
from src.core.constants import admin_actions
from src.services.admin_log_service import AdminLogService
from src.services.class_slot_service import ClassSlotService
from src.services.online_course_service import OnlineCourseService

router = Router()

class_slot_service = ClassSlotService()
online_course_service = OnlineCourseService()
admin_log_service = AdminLogService()
settings = get_settings()

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


@router.callback_query(F.data == "admin_slots")
async def admin_slots_menu(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    slots = class_slot_service.list_active(db)
    if not slots:
        await callback.message.edit_text(
            "🗓 هنوز زمان آزادی ثبت نشده است.\nبا دکمه زیر زمان جدید اضافه کنید.",
            reply_markup=admin_slots_list_keyboard([]),
        )
    else:
        await callback.message.edit_text(
            f"🗓 {len(slots)} زمان فعال:\n(🟢 آزاد / 🔵 پر / ⚫ بسته)",
            reply_markup=admin_slots_list_keyboard(slots),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_slot_view_"))
async def admin_slot_view(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    slot_id = int(callback.data.replace("admin_slot_view_", ""))
    slot = class_slot_service.get_by_id(db, slot_id)
    if not slot:
        await callback.answer("زمان پیدا نشد", show_alert=True)
        return

    course = online_course_service.get_course_by_id(db, slot.online_course_id)
    left = max(0, slot.capacity - slot.booked_count)
    text = (
        f"🗓 زمان #{slot.id}\n\n"
        f"🎼 کلاس: {course.name if course else '—'}\n"
        f"📆 تاریخ: {slot.slot_date}\n"
        f"⏰ ساعت: {slot.slot_time}\n"
        f"ظرفیت: {left} از {slot.capacity}\n"
        f"وضعیت: {slot.status.value}"
    )
    await callback.message.edit_text(text, reply_markup=admin_slot_detail_keyboard(slot.id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_slot_close_"))
async def admin_slot_close(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    slot_id = int(callback.data.replace("admin_slot_close_", ""))
    slot = class_slot_service.close(db, slot_id)
    if not slot:
        await callback.answer("زمان پیدا نشد", show_alert=True)
        return

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.RESERVATION_REJECT,
        f"زمان آزاد #{slot.id} ({slot.slot_date} {slot.slot_time}) بسته شد",
    )
    await callback.message.edit_text(
        callback.message.text + "\n\n🚫 بسته شد.",
        reply_markup=admin_back_button("admin_slots"),
    )
    await callback.answer("بسته شد")


@router.callback_query(F.data == "admin_slot_add")
async def admin_slot_add_start(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    courses = online_course_service.get_active_courses(db)
    if not courses:
        await callback.answer("هیچ کلاس فعالی نیست.", show_alert=True)
        return

    await callback.message.edit_text(
        "کلاس مورد نظر برای زمان آزاد را انتخاب کنید:",
        reply_markup=admin_slot_courses_keyboard(courses),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_slot_course_"))
async def admin_slot_course_picked(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    course_id = int(callback.data.replace("admin_slot_course_", ""))
    await state.update_data(slot_course_id=course_id)
    await state.set_state(AdminState.waiting_slot_date)
    await callback.message.answer(
        "📅 تاریخ را به صورت شمسی بفرستید (مثال: 1404-07-20):"
    )
    await callback.answer()


@router.message(AdminState.waiting_slot_date)
async def admin_slot_date(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return

    text = (message.text or "").strip()
    if not DATE_PATTERN.match(text):
        await message.answer("❌ فرمت تاریخ نادرست است. مثال: 1404-07-20")
        return

    await state.update_data(slot_date=text)
    await state.set_state(AdminState.waiting_slot_time)
    await message.answer("⏰ ساعت را بفرستید (مثال: 18:30):")


@router.message(AdminState.waiting_slot_time)
async def admin_slot_time(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return

    text = (message.text or "").strip()
    if not TIME_PATTERN.match(text):
        await message.answer("❌ فرمت ساعت نادرست است. مثال: 18:30")
        return

    data = await state.get_data()
    course_id = data.get("slot_course_id")
    slot_date = data.get("slot_date")
    await state.clear()

    slot = class_slot_service.publish(
        db=db,
        online_course_id=course_id,
        slot_date=slot_date,
        slot_time=text,
        capacity=1,
    )

    course = online_course_service.get_course_by_id(db, course_id)
    admin_log_service.log(
        db, message.from_user.id, admin_actions.RESERVATION_CONFIRM,
        f"زمان آزاد #{slot.id} برای «{course.name if course else course_id}» "
        f"در {slot_date} ساعت {text} ثبت شد",
    )

    await message.answer(
        f"✅ زمان آزاد ثبت شد:\n🎼 {course.name if course else course_id}\n"
        f"📆 {slot_date}  ⏰ {text}"
    )
