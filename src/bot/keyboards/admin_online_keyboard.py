from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_online_courses_keyboard(courses):

    rows = [
        [
            InlineKeyboardButton(
                text=f"🎼 {course.name}",
                callback_data=f"admin_online_enroll_{course.id}",
            )
        ]
        for course in courses
    ]

    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_model_keyboard(user_id: int, course_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ماهانه",
                    callback_data=f"admin_online_plan_{user_id}_{course_id}_monthly",
                ),
                InlineKeyboardButton(
                    text="ترمی",
                    callback_data=f"admin_online_plan_{user_id}_{course_id}_term",
                ),
            ]
        ]
    )


# ---------------- Online course CRUD (admin management) ----------------


def admin_online_manage_list_keyboard(courses):

    rows = []

    for course in courses:
        status = "✅" if course.is_active else "🚫"
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {course.name}",
                callback_data=f"admin_oc_view_{course.id}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="➕ افزودن کلاس آنلاین جدید", callback_data="admin_oc_new"),
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_online_course_detail_keyboard(course):

    toggle_text = "🚫 غیرفعال کردن" if course.is_active else "✅ فعال کردن"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ نام", callback_data=f"admin_oc_edit_name_{course.id}"),
                InlineKeyboardButton(text="✏️ مدرس", callback_data=f"admin_oc_edit_teacher_{course.id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ مدت جلسه", callback_data=f"admin_oc_edit_duration_minutes_{course.id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ قیمت ماهانه", callback_data=f"admin_oc_edit_monthly_price_{course.id}"),
                InlineKeyboardButton(text="✏️ قیمت ترمی", callback_data=f"admin_oc_edit_term_price_{course.id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ تعداد جلسات ماهانه", callback_data=f"admin_oc_edit_monthly_sessions_{course.id}"),
                InlineKeyboardButton(text="✏️ تعداد جلسات ترم", callback_data=f"admin_oc_edit_term_sessions_{course.id}"),
            ],
            [
                InlineKeyboardButton(text="🕒 مدیریت زمان‌های هفتگی", callback_data=f"admin_oc_slot_{course.id}"),
            ],
            [
                InlineKeyboardButton(text="🚫 غیرفعال کردن", callback_data=f"admin_oc_toggle_{course.id}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_online_manage"),
            ],
        ]
    )
