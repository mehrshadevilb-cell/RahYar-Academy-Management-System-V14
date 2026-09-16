from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from src.database.models.user import UserRole


def get_main_menu(role: UserRole | None = None):
    keyboard = [
        [KeyboardButton(text="📚 دوره ها")],
        [KeyboardButton(text="🎓 دوره های من")],
        [KeyboardButton(text="🎼 کلاس آنلاین")],
        [KeyboardButton(text="🎵 AI Generator")],
        [KeyboardButton(text="📝 تکالیف")],
        [KeyboardButton(text="📈 پیشرفت من")],
        [KeyboardButton(text="👤 پروفایل"), KeyboardButton(text="🔔 اعلان‌ها")],
        [KeyboardButton(text="🎁 دعوت از دوستان")],
        [KeyboardButton(text="🤖 دستیار هوشمند"), KeyboardButton(text="🆘 پشتیبانی")],
    ]
    if role == UserRole.ADMIN:
        keyboard.append([KeyboardButton(text="🛠 پنل مدیریت")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
