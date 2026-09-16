from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 گزارش امروز",
                    callback_data="admin_dashboard",
                ),
                InlineKeyboardButton(
                    text="🩺 وضعیت سیستم",
                    callback_data="admin_system_health",
                ),
            ],
            [
                InlineKeyboardButton(text="📚 محصولات", callback_data="admin_products"),
                InlineKeyboardButton(text="💳 پرداخت‌های در انتظار", callback_data="admin_pending"),
            ],
            [
                InlineKeyboardButton(text="🏦 کارت‌های پرداخت", callback_data="admin_cards"),
                InlineKeyboardButton(text="🧪 تست SpotPlayer", callback_data="admin_spotplayer_test"),
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
                InlineKeyboardButton(text="🆘 پشتیبانی", callback_data="admin_support"),
                InlineKeyboardButton(text="📝 تکالیف", callback_data="admin_assignments"),
            ],
            [InlineKeyboardButton(text="🧠 AI Developer Agent", callback_data="admin_ai")],
        ]
    )


def admin_back_button(callback_data: str = "admin_home"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ بازگشت", callback_data=callback_data)]]
    )
