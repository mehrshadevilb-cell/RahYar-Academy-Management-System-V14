from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.core.utils.jalali import (
    JALALI_MONTH_NAMES,
    JALALI_WEEKDAY_LETTERS,
    jalali_month_length,
    jalali_weekday_index,
    add_months,
    today_jalali,
    is_past_jalali_date,
)

# How many months ahead of the current one a student may browse to when
# picking a reservation date - keeps the picker from scrolling forever
# into dates the academy hasn't scheduled anything for yet.
MAX_MONTHS_AHEAD = 6

NOOP = "jcal:noop"


def jalali_calendar_keyboard(enrollment_id: int, jy: int, jm: int) -> InlineKeyboardMarkup:
    """
    Renders a month grid for (jy, jm). Days before today are shown but
    disabled (tapping them is a no-op); navigation is clamped so the
    student can't page back before the current month or more than
    `MAX_MONTHS_AHEAD` months into the future.
    """

    rows = []

    today_jy, today_jm, _ = today_jalali()
    max_jy, max_jm = add_months(today_jy, today_jm, MAX_MONTHS_AHEAD)

    prev_jy, prev_jm = add_months(jy, jm, -1)
    next_jy, next_jm = add_months(jy, jm, 1)

    can_go_back = (jy, jm) > (today_jy, today_jm)
    can_go_forward = (jy, jm) < (max_jy, max_jm)

    nav_row = [
        InlineKeyboardButton(
            text="◀️" if can_go_back else " ",
            callback_data=(
                f"jcal:nav:{enrollment_id}:{prev_jy}:{prev_jm}" if can_go_back else NOOP
            ),
        ),
        InlineKeyboardButton(
            text=f"{JALALI_MONTH_NAMES[jm - 1]} {jy}",
            callback_data=NOOP,
        ),
        InlineKeyboardButton(
            text="▶️" if can_go_forward else " ",
            callback_data=(
                f"jcal:nav:{enrollment_id}:{next_jy}:{next_jm}" if can_go_forward else NOOP
            ),
        ),
    ]
    rows.append(nav_row)

    rows.append([
        InlineKeyboardButton(text=letter, callback_data=NOOP)
        for letter in JALALI_WEEKDAY_LETTERS
    ])

    first_weekday = jalali_weekday_index(jy, jm, 1)
    month_length = jalali_month_length(jy, jm)

    cells: list[int | None] = [None] * first_weekday + list(range(1, month_length + 1))
    while len(cells) % 7 != 0:
        cells.append(None)

    for week_start in range(0, len(cells), 7):
        week_row = []

        for day in cells[week_start:week_start + 7]:
            if day is None:
                week_row.append(InlineKeyboardButton(text=" ", callback_data=NOOP))
            elif is_past_jalali_date(jy, jm, day):
                week_row.append(InlineKeyboardButton(text="·", callback_data=NOOP))
            else:
                week_row.append(
                    InlineKeyboardButton(
                        text=str(day),
                        callback_data=f"jcal:pick:{enrollment_id}:{jy}:{jm}:{day}",
                    )
                )

        rows.append(week_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)
