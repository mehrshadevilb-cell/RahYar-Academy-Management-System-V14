import pytest

from src.bot.handlers.start import normalize_iranian_mobile


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("09121234567", "09121234567"),
        ("+989121234567", "09121234567"),
        ("00989121234567", "09121234567"),
        ("989121234567", "09121234567"),
        ("9121234567", "09121234567"),
        ("+98 912-123-4567", "09121234567"),
        ("۰۹۱۲۱۲۳۴۵۶۷", "09121234567"),
    ],
)
def test_normalize_iranian_mobile_formats(raw, expected):
    assert normalize_iranian_mobile(raw) == expected


def test_normalize_iranian_mobile_rejects_invalid_values():
    assert normalize_iranian_mobile("12345") is None
    assert normalize_iranian_mobile("+14155552671") is None
    assert normalize_iranian_mobile(None) is None
