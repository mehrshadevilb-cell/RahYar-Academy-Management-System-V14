from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


CANCEL_BUTTON = InlineKeyboardButton(text="❌ انصراف", callback_data="music_cancel")


def generator_panel_keyboard() -> InlineKeyboardMarkup:
    """Compact AI Generator entry panel for Telegram groups."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎵 ساخت Audio", callback_data="music_open:audio")],
            [InlineKeyboardButton(text="🎹 ساخت MIDI", callback_data="music_open:midi")],
            [InlineKeyboardButton(text="✨ AI انتخاب کند", callback_data="music_open:auto")],
        ]
    )


def output_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔊 Audio", callback_data="music_output:audio")],
            [InlineKeyboardButton(text="🎹 MIDI", callback_data="music_output:midi")],
            [InlineKeyboardButton(text="✨ خودت انتخاب کن", callback_data="music_output:auto")],
            [InlineKeyboardButton(text="⚙️ تنظیمات پیشرفته", callback_data="music_advanced")],
            [CANCEL_BUTTON],
        ]
    )


def advanced_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎚 BPM", callback_data="music_adv:bpm")],
            [InlineKeyboardButton(text="🎼 Key / Scale", callback_data="music_adv:key")],
            [InlineKeyboardButton(text="⏱ Duration / Bars", callback_data="music_adv:length")],
            [InlineKeyboardButton(text="🎹 Instruments / Style", callback_data="music_adv:style")],
            [InlineKeyboardButton(text="♻️ Reset تنظیمات", callback_data="music_adv:reset")],
            [InlineKeyboardButton(text="🚀 Generate", callback_data="music_adv:generate")],
            [InlineKeyboardButton(text="↩️ بازگشت", callback_data="music_adv:back")],
        ]
    )


def after_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔊 Preview / ارسال دوباره", callback_data="music_preview")],
            [InlineKeyboardButton(text="🔁 Variation", callback_data="music_variation")],
            [InlineKeyboardButton(text="➕ Extend", callback_data="music_extend")],
            [InlineKeyboardButton(text="✏️ Edit Prompt", callback_data="music_edit_prompt")],
            [InlineKeyboardButton(text="⚙️ Advanced", callback_data="music_advanced")],
            [InlineKeyboardButton(text="🆕 Prompt جدید", callback_data="music_restart")],
        ]
    )
