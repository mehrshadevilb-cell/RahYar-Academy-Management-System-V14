from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from src.database.models.user import UserRole


def get_main_menu(role: UserRole | None = None):

    keyboard = [
        [KeyboardButton(text="📚 دوره ها")],
        [KeyboardButton(text="🎓 دوره های من")],
        [KeyboardButton(text="🎼 کلاس آنلاین")],
        [KeyboardButton(text="📝 تکالیف")],
        [KeyboardButton(text="👤 پروفایل")],
        [KeyboardButton(text="🎁 دعوت از دوستان")],
        [KeyboardButton(text="🆘 پشتیبانی")],
    ]

    if role == UserRole.ADMIN:
        keyboard.append([KeyboardButton(text="🛠 پنل مدیریت")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
