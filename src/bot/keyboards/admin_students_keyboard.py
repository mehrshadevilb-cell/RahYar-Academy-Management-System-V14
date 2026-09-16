from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.student_admin_service import StudentFilter, StudentListItem


def students_home_keyboard(counts: dict[str, int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📋 همه ({counts.get('total', 0)})",
                    callback_data="stu_list_all_0",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📱 تلگرام ({counts.get('telegram', 0)})",
                    callback_data="stu_list_tg_0",
                ),
                InlineKeyboardButton(
                    text=f"📥 اسپات/قدیم ({counts.get('legacy', 0)})",
                    callback_data="stu_list_legacy_0",
                ),
            ],
            [InlineKeyboardButton(text="🔍 جستجو نام/شماره", callback_data="stu_search")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )


def students_list_keyboard(
    items: list[StudentListItem],
    filt: str,
    page: int,
    total: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        label = item.full_name[:28] or f"#{item.user_id}"
        prefix = "📱" if item.has_telegram else "📥"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix} {label}",
                    callback_data=f"stu_view_{item.user_id}_{filt}_{page}",
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبل", callback_data=f"stu_list_{filt}_{page - 1}"))
    max_page = max(0, (total - 1) // page_size) if total else 0
    if page < max_page:
        nav.append(InlineKeyboardButton(text="بعد ➡️", callback_data=f"stu_list_{filt}_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🏠 منوی هنرجوها", callback_data="admin_students")])
    rows.append([InlineKeyboardButton(text="⬅️ پنل ادمین", callback_data="admin_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def student_detail_keyboard(user_id: int, filt: str, page: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "🚫 غیرفعال‌سازی" if is_active else "✅ فعال‌سازی"
    toggle_data = f"stu_toggle_{user_id}_{0 if is_active else 1}_{filt}_{page}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
            [InlineKeyboardButton(text="⬅️ لیست", callback_data=f"stu_list_{filt}_{page}")],
            [InlineKeyboardButton(text="🏠 منوی هنرجوها", callback_data="admin_students")],
        ]
    )
