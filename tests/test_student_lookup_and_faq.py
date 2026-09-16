from src.bot.handlers.faq_quick import match_faq
from src.services.student_lookup_service import StudentLookupService


def test_faq_matches_license_question():
    assert match_faq("لایسنسم کجاست؟") is not None
    assert "لایسنس" in match_faq("کد دوره اسپات")


def test_faq_ignores_unrelated():
    assert match_faq("سلام") is None
    assert match_faq("") is None


def test_student_lookup_service_instantiates():
    assert StudentLookupService() is not None
