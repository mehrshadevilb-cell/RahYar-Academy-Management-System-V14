from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📚 محصولات", callback_data="admin_products"),
                InlineKeyboardButton(text="💳 پرداخت‌های در انتظار", callback_data="admin_pending"),
            ],
            [
                InlineKeyboardButton(text="🏦 کارت‌های پرداخت", callback_data="admin_cards"),
                InlineKeyboardButton(text="📊 آمار", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton(text="🎼 ثبت‌نام در کلاس آنلاین", callback_data="admin_online"),
                InlineKeyboardButton(text="⚙️ مدیریت کلاس‌های آنلاین", callback_data="admin_online_manage"),
            ],
            [
                InlineKeyboardButton(text="📅 رزروهای در انتظار", callback_data="admin_reservations"),
                InlineKeyboardButton(text="💰 اقساط", callback_data="admin_installments"),
            ],
            [
                InlineKeyboardButton(text="🎁 کدهای تخفیف", callback_data="admin_discounts"),
                InlineKeyboardButton(text="📜 لاگ ادمین", callback_data="admin_logs"),
            ],
            [
                InlineKeyboardButton(text="📢 پیام همگانی", callback_data="admin_broadcast"),
                InlineKeyboardButton(text="📊 خروجی گزارش‌ها", callback_data="admin_reports"),
            ],
            [
                InlineKeyboardButton(text="❓ آزمون‌ها", callback_data="admin_quizzes"),
                InlineKeyboardButton(text="🧠 AI Developer Agent", callback_data="admin_ai"),
            ],
        ]
    )


def admin_back_button(callback_data: str = "admin_home"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ بازگشت", callback_data=callback_data)]]
    )
