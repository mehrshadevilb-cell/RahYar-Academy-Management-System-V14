"""
Pure-Python Gregorian <-> Jalali (Persian/Iranian) calendar conversion.

No third-party dependency is used here on purpose: this is a small,
self-contained, well-understood algorithm, and adding a package just for
date-math the project can own outright (and fully test) isn't worth the
extra dependency per PROJECT_CONTEXT.md §46.

Correctness has been verified in this project by:
- Round-tripping every single day from 1940-01-01 to 2060-12-31 through
  gregorian_to_jalali -> jalali_to_gregorian with zero mismatches.
- The well-known anchor date: 1979-02-11 (Gregorian) = 22 Bahman 1357
  (the Iranian Revolution).
See tests/test_jalali.py for both.
"""

from datetime import date, timedelta


def _div(a: int, b: int) -> int:
    return a // b


_G_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_J_DAYS_IN_MONTH = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

JALALI_MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# Persian week starts on Saturday. Index 0 = Saturday .. index 6 = Friday.
JALALI_WEEKDAY_LETTERS = ["ش", "ی", "د", "س", "چ", "پ", "ج"]


def _is_gregorian_leap(gy: int) -> bool:
    return (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)


def _month_and_day_from_dayno(day_no: int, month_lengths: list[int]) -> tuple[int, int]:
    """
    Given a 0-indexed day-of-year offset and a list of month lengths,
    returns (month, day), both 1-indexed. The last month absorbs
    whatever remains, so no special-casing is needed for it here - the
    caller is responsible for that table entry already having the right
    length (e.g. 29 vs 30 for Esfand in a leap year).
    """

    for i in range(len(month_lengths) - 1):
        if day_no < month_lengths[i]:
            return i + 1, day_no + 1
        day_no -= month_lengths[i]

    return len(month_lengths), day_no + 1


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = 365 * gy2 + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400)

    for i in range(gm2):
        g_day_no += _G_DAYS_IN_MONTH[i]
        if i == 1 and _is_gregorian_leap(gy):
            g_day_no += 1

    g_day_no += gd2

    j_day_no = g_day_no - 79

    j_np = _div(j_day_no, 12053)
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * _div(j_day_no, 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += _div(j_day_no - 1, 365)
        j_day_no = (j_day_no - 1) % 365

    jm, jd = _month_and_day_from_dayno(j_day_no, _J_DAYS_IN_MONTH)

    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    jy2 = jy - 979

    j_day_no = 365 * jy2 + _div(jy2, 33) * 8 + _div(jy2 % 33 + 3, 4)

    for i in range(jm - 1):
        j_day_no += _J_DAYS_IN_MONTH[i]

    j_day_no += jd - 1

    g_day_no = j_day_no + 79

    gy = 1600 + 400 * _div(g_day_no, 146097)
    g_day_no %= 146097

    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * _div(g_day_no, 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False

    gy += 4 * _div(g_day_no, 1461)
    g_day_no %= 1461

    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += _div(g_day_no, 365)
        g_day_no %= 365

    g_months = [
        length + (1 if i == 1 and leap else 0)
        for i, length in enumerate(_G_DAYS_IN_MONTH)
    ]
    gm, gd = _month_and_day_from_dayno(g_day_no, g_months)

    return gy, gm, gd


def today_jalali() -> tuple[int, int, int]:
    today = date.today()
    return gregorian_to_jalali(today.year, today.month, today.day)


def is_jalali_leap_year(jy: int) -> bool:
    """A Jalali year is leap iff its 12th month (Esfand) has 30 days,
    which we determine by round-tripping day 30 of month 12 rather than
    re-deriving a separate leap-year formula - if (jy, 12, 30) converts
    to Gregorian and back to the exact same Jalali date, that day
    genuinely exists in this year."""

    gy, gm, gd = jalali_to_gregorian(jy, 12, 30)
    return gregorian_to_jalali(gy, gm, gd) == (jy, 12, 30)


def jalali_month_length(jy: int, jm: int) -> int:
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_jalali_leap_year(jy) else 29


def jalali_weekday_index(jy: int, jm: int, jd: int) -> int:
    """0 = Saturday .. 6 = Friday (start of the Persian week)."""

    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    # Python's date.weekday(): 0 = Monday .. 6 = Sunday.
    python_weekday = date(gy, gm, gd).weekday()
    return (python_weekday + 2) % 7


def format_jalali_date(jy: int, jm: int, jd: int) -> str:
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def add_months(jy: int, jm: int, delta: int) -> tuple[int, int]:
    """Shifts (jy, jm) by `delta` months, wrapping the year as needed."""

    zero_based = (jm - 1) + delta
    jy += zero_based // 12
    jm = zero_based % 12 + 1
    return jy, jm


def is_past_jalali_date(jy: int, jm: int, jd: int) -> bool:
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    return date(gy, gm, gd) < date.today()
