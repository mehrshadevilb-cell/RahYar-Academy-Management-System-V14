from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.database.models.class_slot import ClassSlot


def student_slots_keyboard(
    enrollment_id: int, slots: list[ClassSlot]
) -> InlineKeyboardMarkup:
    rows = []
    for s in slots:
        label = f"📅 {s.slot_date} ⏰ {s.slot_time}"
        if s.capacity > 1:
            label += f" ({s.booked_count}/{s.capacity})"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"slot_pick_{enrollment_id}_{s.id}",
                )
            ]
        )
    if not rows:
        rows = [[InlineKeyboardButton(text="زمان آزادی نیست", callback_data="noop")]]
    rows.append([InlineKeyboardButton(text="❌ انصراف", callback_data="slot_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_slots_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ افزودن زمان آزاد",
                    callback_data="admin_slot_add",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 لیست زمان‌ها",
                    callback_data="admin_slot_list",
                )
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )


def admin_slot_list_keyboard(slots: list[ClassSlot]) -> InlineKeyboardMarkup:
    rows = []
    for s in slots[:25]:
        status = "🟢" if s.is_available else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} #{s.id} {s.slot_date} {s.slot_time}",
                    callback_data=f"admin_slot_close_{s.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_slots")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
