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
    rows.append(
        [InlineKeyboardButton(text="👥 مدیریت ثبت‌نام‌ها", callback_data="admin_oe_manage_pick")]
    )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_student_picker_keyboard(course_id: int, students, page: int, total: int, page_size: int = 15):
    rows = []
    for student in students:
        label = student.full_name or f"کاربر #{student.id}"
        phone = f" · {student.phone}" if student.phone else ""
        rows.append([
            InlineKeyboardButton(
                text=f"👤 {label}{phone}",
                callback_data=f"aoes_{course_id}_{student.id}",
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"aoep_{course_id}_{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"aoep_{course_id}_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton(
            text="🔎 جستجو با شماره / کد هنرجو",
            callback_data=f"aoesearch_{course_id}",
        )
    ])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_online")])
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
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data=f"admin_online_enroll_{course_id}")],
        ]
    )


def admin_course_enrollments_keyboard(course_id: int, enrollments, profiles_by_id: dict):
    rows = []
    for enr in enrollments:
        student = profiles_by_id.get(enr.user_id)
        name = student.full_name if student else f"#{enr.user_id}"
        status = {"active": "✅", "paused": "⏸", "ended": "⏹"}.get(enr.status.value, "?")
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {name} · {enr.remaining_sessions} جلسه",
                callback_data=f"aoeview_{enr.id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_online")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_enrollment_detail_keyboard(enrollment):
    eid = enrollment.id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖ ۱ جلسه", callback_data=f"aoesess_{eid}_-1"),
                InlineKeyboardButton(text="➕ ۱ جلسه", callback_data=f"aoesess_{eid}_1"),
            ],
            [
                InlineKeyboardButton(text="➕ ۴ جلسه", callback_data=f"aoesess_{eid}_4"),
                InlineKeyboardButton(text="✏️ تعداد دلخواه", callback_data=f"aoeset_{eid}"),
            ],
            [
                InlineKeyboardButton(text="💰 هزینه دستی", callback_data=f"aoefee_{eid}"),
                InlineKeyboardButton(text="📝 یادداشت", callback_data=f"aoenote_{eid}"),
            ],
            [
                InlineKeyboardButton(text="⏸ توقف", callback_data=f"aoestatus_{eid}_paused"),
                InlineKeyboardButton(text="✅ فعال", callback_data=f"aoestatus_{eid}_active"),
                InlineKeyboardButton(text="⏹ پایان", callback_data=f"aoestatus_{eid}_ended"),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ لیست ثبت‌نام‌ها",
                    callback_data=f"aom_{enrollment.online_course_id}",
                )
            ],
        ]
    )


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
                InlineKeyboardButton(
                    text="✏️ مدت جلسه",
                    callback_data=f"admin_oc_edit_duration_minutes_{course.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ قیمت ماهانه",
                    callback_data=f"admin_oc_edit_monthly_price_{course.id}",
                ),
                InlineKeyboardButton(
                    text="✏️ قیمت ترمی",
                    callback_data=f"admin_oc_edit_term_price_{course.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ تعداد جلسات ماهانه",
                    callback_data=f"admin_oc_edit_monthly_sessions_{course.id}",
                ),
                InlineKeyboardButton(
                    text="✏️ تعداد جلسات ترم",
                    callback_data=f"admin_oc_edit_term_sessions_{course.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🕒 مدیریت زمان‌های هفتگی",
                    callback_data=f"admin_oc_slot_{course.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 هنرجویان این کلاس",
                    callback_data=f"aom_{course.id}",
                ),
            ],
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"admin_oc_toggle_{course.id}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_online_manage"),
            ],
        ]
    )


def online_purchase_review_keyboard(user_id: int, course_id: int, plan: str, amount: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ تایید و ثبت‌نام",
                    callback_data=f"ocpay_ok_{user_id}_{course_id}_{plan}_{amount}",
                ),
                InlineKeyboardButton(
                    text="❌ رد",
                    callback_data=f"ocpay_no_{user_id}_{course_id}",
                ),
            ]
        ]
    )
