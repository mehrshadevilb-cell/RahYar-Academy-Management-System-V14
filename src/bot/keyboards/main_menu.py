from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from src.core.config.settings import get_settings
from src.database.models.user import UserRole


def get_main_menu(role: UserRole | None = None):
    keyboard = [
        [KeyboardButton(text="📚 دوره ها")],
        [KeyboardButton(text="🎓 دوره های من")],
        [KeyboardButton(text="🧾 وضعیت پرداخت")],
        [KeyboardButton(text="🎼 کلاس آنلاین")],
        [KeyboardButton(text="🎵 AI Generator")],
        [KeyboardButton(text="📝 تکالیف")],
        [KeyboardButton(text="📈 پیشرفت من")],
        [KeyboardButton(text="👤 پروفایل")],
        [KeyboardButton(text="🎁 دعوت از دوستان")],
        [KeyboardButton(text="🤖 دستیار هوشمند"), KeyboardButton(text="🆘 پشتیبانی")],
    ]
    web_app_url = get_settings().telegram_web_app_url
    if web_app_url:
        keyboard.insert(0, [KeyboardButton(text="🌐 ورود به سایت آکادمی", web_app=WebAppInfo(url=web_app_url))])
    if role == UserRole.ADMIN:
        keyboard.append([KeyboardButton(text="🛠 پنل مدیریت")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
