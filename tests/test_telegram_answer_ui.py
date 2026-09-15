from src.services.telegram_answer_ui import format_assistant_answer


def test_format_assistant_answer_renders_sections_and_lists():
    result = format_assistant_answer(
        "## جواب\n\nبرای تنظیمش:\n1️⃣ مسیر را باز کن\n2️⃣ مقدار را تغییر بده\n\n**نکته:** قبل از خروج ذخیره کن"
    )

    assert result.startswith("🤖 <b>راه‌یار</b>")
    assert "<b>🎯 جواب</b>" in result
    assert "1️⃣ مسیر را باز کن" in result
    assert "<b>نکته:</b>" in result


def test_format_assistant_answer_never_exceeds_safe_telegram_budget():
    result = format_assistant_answer("x " * 3000)
    assert len(result) <= 3900 + len("🤖 <b>راه‌یار</b>\n\n")
    assert result.endswith("…")
