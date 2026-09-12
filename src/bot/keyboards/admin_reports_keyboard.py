from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_reports_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 گزارش پرداخت‌ها", callback_data="report_payments"),
            ],
            [
                InlineKeyboardButton(text="👥 گزارش هنرجویان", callback_data="report_students"),
            ],
            [
                InlineKeyboardButton(
                    text="🎼 گزارش ثبت‌نام کلاس‌های آنلاین",
                    callback_data="report_online_enrollments",
                ),
            ],
            [
                InlineKeyboardButton(text="💰 گزارش اقساط", callback_data="report_installments"),
            ],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home"),
            ],
        ]
    )
