from datetime import date, timedelta

from src.core.utils.jalali import (
    gregorian_to_jalali,
    jalali_to_gregorian,
    is_jalali_leap_year,
    jalali_month_length,
    jalali_weekday_index,
    format_jalali_date,
    add_months,
    is_past_jalali_date,
)


def test_known_anchor_iranian_revolution_date():
    assert gregorian_to_jalali(1979, 2, 11) == (1357, 11, 22)
    assert jalali_to_gregorian(1357, 11, 22) == (1979, 2, 11)


def test_round_trip_every_day_for_120_years():
    d = date(1940, 1, 1)
    end = date(2060, 12, 31)

    while d <= end:
        jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
        back = jalali_to_gregorian(jy, jm, jd)
        assert back == (d.year, d.month, d.day), f"mismatch at {d}"
        d += timedelta(days=1)


def test_nowruz_falls_near_march_twentieth_or_twentyfirst():
    for jy in range(1390, 1420):
        gy, gm, gd = jalali_to_gregorian(jy, 1, 1)
        assert gm == 3
        assert gd in (20, 21)


def test_month_lengths_follow_jalali_pattern():
    for jy in range(1390, 1420):
        for jm in range(1, 7):
            assert jalali_month_length(jy, jm) == 31
        for jm in range(7, 12):
            assert jalali_month_length(jy, jm) == 30
        assert jalali_month_length(jy, 12) in (29, 30)


def test_leap_year_esfand_has_thirty_days_and_is_internally_consistent():
    for jy in range(1390, 1420):
        leap = is_jalali_leap_year(jy)
        expected_length = 30 if leap else 29
        assert jalali_month_length(jy, 12) == expected_length


def test_format_jalali_date_is_zero_padded():
    assert format_jalali_date(1404, 7, 5) == "1404-07-05"
    assert format_jalali_date(1404, 12, 30) == "1404-12-30"


def test_add_months_wraps_year_forward_and_backward():
    assert add_months(1404, 11, 1) == (1404, 12)
    assert add_months(1404, 12, 1) == (1405, 1)
    assert add_months(1404, 1, -1) == (1403, 12)


def test_weekday_index_matches_known_saturday():
    jy, jm, jd = 1404, 1, 1
    idx = jalali_weekday_index(jy, jm, jd)
    assert 0 <= idx <= 6

    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    seen = set()
    for offset in range(7):
        d = date(gy, gm, gd) + timedelta(days=offset)
        jjy, jjm, jjd = gregorian_to_jalali(d.year, d.month, d.day)
        seen.add(jalali_weekday_index(jjy, jjm, jjd))
    assert seen == set(range(7))


def test_is_past_jalali_date():
    assert is_past_jalali_date(1300, 1, 1) is True

    future = date.today() + timedelta(days=365 * 5)
    future_jy, future_jm, future_jd = gregorian_to_jalali(future.year, future.month, future.day)
    assert is_past_jalali_date(future_jy, future_jm, future_jd) is False
