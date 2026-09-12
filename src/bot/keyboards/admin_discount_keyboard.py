from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.database.models.discount_code import DiscountType


def admin_discounts_keyboard(codes):

    rows = []

    for code in codes:

        status = "✅" if code.is_active else "🚫"

        value_label = (
            f"{code.value}٪"
            if code.discount_type == DiscountType.PERCENTAGE
            else f"{code.value:,} ت"
        )

        usage_label = (
            f"{code.used_count}/{code.max_uses}"
            if code.max_uses is not None
            else f"{code.used_count}/∞"
        )

        rows.append([
            InlineKeyboardButton(
                text=f"{status} {code.code} ({value_label}) - {usage_label}",
                callback_data=f"admin_discount_view_{code.id}",
            )
        ])

    rows.append([
        InlineKeyboardButton(text="➕ کد تخفیف جدید", callback_data="admin_discount_add"),
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_discount_detail_keyboard(code):

    toggle_text = "🚫 غیرفعال کردن" if code.is_active else "✅ فعال کردن"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin_discount_toggle_{code.id}",
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_discounts"),
            ],
        ]
    )


def admin_discount_type_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="٪ درصدی",
                    callback_data="admin_discount_type_percentage",
                ),
                InlineKeyboardButton(
                    text="تومان ثابت",
                    callback_data="admin_discount_type_fixed",
                ),
            ],
        ]
    )
