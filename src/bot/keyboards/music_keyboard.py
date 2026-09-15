from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


CANCEL_BUTTON = InlineKeyboardButton(text="❌ انصراف", callback_data="music_cancel")


def output_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔊 Audio", callback_data="music_output:audio")],
            [InlineKeyboardButton(text="🎹 MIDI", callback_data="music_output:midi")],
            [InlineKeyboardButton(text="✨ خودت انتخاب کن", callback_data="music_output:auto")],
            [CANCEL_BUTTON],
        ]
    )


def after_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Variation", callback_data="music_variation")],
            [InlineKeyboardButton(text="🆕 Prompt جدید", callback_data="music_restart")],
        ]
    )
