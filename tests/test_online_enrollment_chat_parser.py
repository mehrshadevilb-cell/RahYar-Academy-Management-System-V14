from src.services.online_enrollment_chat_parser import parse_enrollment_chat


def test_parse_mahdi_example():
    text = (
        "مهدی متاج با شماره 09370745337 هر سه‌شنبه ساعت 4 تا 6 "
        "کلاس تنظیم میکس و مسترینگ داره و 2 جلسه دیگه داره تا تکمیل دوره"
    )
    draft = parse_enrollment_chat(text)
    assert draft.phone == "09370745337"
    assert draft.remaining_sessions == 2
    assert draft.weekday == "سه‌شنبه"
    assert draft.time_from == "04:00"
    assert draft.time_to == "06:00"
    assert draft.course_hint is not None
    assert "میکس" in draft.course_hint or "تنظیم" in draft.course_hint


def test_parse_twelve_weeks():
    text = "علی رضایی 09121234567 ثبت نام کرد 12 جلسه برای شنبه‌ها ساعت 10 تا 12 برای 12 هفته"
    draft = parse_enrollment_chat(text)
    assert draft.phone == "09121234567"
    assert draft.remaining_sessions == 12
    assert draft.weeks == 12
    assert draft.weekday == "شنبه"
