from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_products_keyboard(courses):

    rows = []

    for course in courses:

        status = "✅" if course.is_active else "🚫"

        rows.append([
            InlineKeyboardButton(
                text=f"{status} {course.title} - {course.price:,} تومان",
                callback_data=f"admin_product_view_{course.id}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_detail_keyboard(course):

    toggle_text = "🚫 غیرفعال کردن" if course.is_active else "✅ فعال کردن"

    integration_button = (
        InlineKeyboardButton(
            text="🔌 مدیریت کدهای SpotPlayer",
            callback_data=f"admin_product_spotplayer_{course.id}",
        )
        if course.delivery_type.value == "spotplayer"
        else InlineKeyboardButton(
            text="📡 مدیریت کانال‌های تلگرام",
            callback_data=f"admin_product_channels_{course.id}",
        )
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin_product_toggle_{course.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 تغییر قیمت",
                    callback_data=f"admin_product_price_{course.id}",
                ),
            ],
            [integration_button],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_products"),
            ],
        ]
    )


def spotplayer_courses_keyboard(product_id: int, records):

    rows = []

    for record in records:
        status = "✅" if record.enabled else "🚫"
        label = record.course_name or record.spotplayer_course_id
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {label}",
                callback_data=f"admin_sp_toggle_{record.id}",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="➕ افزودن کد دوره SpotPlayer",
            callback_data=f"admin_sp_add_{product_id}",
        )
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ بازگشت", callback_data=f"admin_product_view_{product_id}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def telegram_channels_keyboard(product_id: int, records):

    rows = []

    for record in records:
        status = "✅" if record.enabled else "🚫"
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {record.name}",
                callback_data=f"admin_ch_toggle_{record.id}",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="➕ افزودن کانال تلگرام",
            callback_data=f"admin_ch_add_{product_id}",
        )
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ بازگشت", callback_data=f"admin_product_view_{product_id}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
