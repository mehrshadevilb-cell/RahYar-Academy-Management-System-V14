from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def student_open_slots_keyboard(slots, enrollment_id: int):
    rows = []
    for slot in slots:
        left = max(0, slot.capacity - slot.booked_count)
        rows.append([
            InlineKeyboardButton(
                text=f"📆 {slot.slot_date}  ⏰ {slot.slot_time}  ({left} جا)",
                callback_data=f"slot_pick_{enrollment_id}_{slot.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="📅 انتخاب تاریخ دلخواه (تقویم)",
            callback_data=f"reserve_{enrollment_id}",
        )
    ])
    rows.append([InlineKeyboardButton(text="⬅️ انصراف", callback_data="slot_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_slots_list_keyboard(slots):
    rows = []
    for slot in slots:
        status = {
            "open": "🟢",
            "booked": "🔵",
            "closed": "⚫",
        }.get(slot.status.value if hasattr(slot.status, "value") else str(slot.status), "?")
        left = max(0, slot.capacity - slot.booked_count)
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {slot.slot_date} {slot.slot_time} ({left}/{slot.capacity})",
                callback_data=f"admin_slot_view_{slot.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="➕ افزودن زمان آزاد", callback_data="admin_slot_add"),
    ])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_slot_detail_keyboard(slot_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚫 بستن این زمان",
                    callback_data=f"admin_slot_close_{slot_id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_slots")],
        ]
    )


def admin_slot_courses_keyboard(courses):
    rows = [
        [
            InlineKeyboardButton(
                text=f"🎼 {c.name}",
                callback_data=f"admin_slot_course_{c.id}",
            )
        ]
        for c in courses
    ]
    rows.append([InlineKeyboardButton(text="⬅️ انصراف", callback_data="admin_slots")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
