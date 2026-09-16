from src.services.attendance_service import FREE_ABSENCES_PER_TERM, DEFAULT_TERM_SIZE
from src.services.class_management_chat_service import ClassManagementChatService, ClassChatIntent
from src.services.online_enrollment_chat_parser import parse_enrollment_chat


def test_absence_constants():
    assert FREE_ABSENCES_PER_TERM == 1
    assert DEFAULT_TERM_SIZE == 12


def test_detect_absent_intent():
    svc = ClassManagementChatService()
    assert svc.detect_intent("علی امروز غیبت کرد") == ClassChatIntent.ABSENT
    assert svc.detect_intent("سارا امروز حاضر بود") == ClassChatIntent.PRESENT


def test_parse_enroll_still_works():
    d = parse_enrollment_chat(
        "مهدی 09370745337 هر سه‌شنبه ساعت 4 تا 6 تنظیم میکس 2 جلسه دیگه"
    )
    assert d.phone == "09370745337"
    assert d.remaining_sessions == 2
