"""Inline keyboards for the music generator flow.

Kept separate from the handler so the handler stays focused on flow
logic. Quick-pick buttons exist because roman-numeral progression
notation ("i - iv - v - iv") is music-theory jargon a student may not
know how to type even if they know what sound they want - tapping a
labeled preset removes that barrier entirely, while a free-text option
stays available for anyone who does know the notation.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CANCEL_BUTTON = InlineKeyboardButton(text="❌ انصراف", callback_data="music_cancel")

COMMON_KEYS = ["Am", "Cm", "Dm", "Em", "C", "G", "D", "F"]

COMMON_PROGRESSIONS = [
    ("i - iv - v - iv (مینور، حال و هوای تلخ/trap)", "i - iv - v - iv"),
    ("i - VI - III - VII (مینور، حماسی/سینمایی)", "i - VI - III - VII"),
    ("I - V - vi - IV (ماژور، پاپ)", "I - V - vi - IV"),
    ("ii - V - I (جاز، ماژور)", "ii - V - I"),
]


def key_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for key in COMMON_KEYS:
        row.append(InlineKeyboardButton(text=key, callback_data=f"musickey:{key}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✍️ تایپ کلید دیگر", callback_data="musickey_custom")])
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def progression_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"musicprog:{value}")]
        for label, value in COMMON_PROGRESSIONS
    ]
    rows.append([InlineKeyboardButton(text="✍️ تایپ پیشرفت دیگر", callback_data="musicprog_custom")])
    rows.append([CANCEL_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def instrument_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎸 ریف گیتار نایلون", callback_data="music_guitar")],
            [InlineKeyboardButton(text="🎹 آکورد پیانو (ساده)", callback_data="music_piano_close")],
            [InlineKeyboardButton(text="🎹 آکورد پیانو (جاز)", callback_data="music_piano_jazz")],
            [CANCEL_BUTTON],
        ]
    )


def after_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 ساخت یکی دیگر", callback_data="music_restart")],
        ]
    )
