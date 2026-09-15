from unittest.mock import MagicMock

import pytest

from src.services.chat_assistant_service import (
    BOT_GUIDE_FA,
    SYSTEM_PROMPT_FA,
    ChatAssistantError,
    ChatAssistantService,
    _question_guidance,
)


def _disabled_service():
    service = ChatAssistantService()
    service.settings = MagicMock()
    service.settings.CHAT_ASSISTANT_ENABLED = False
    return service


def test_answer_disabled_raises():
    service = _disabled_service()
    with pytest.raises(ChatAssistantError, match="disabled"):
        service.answer(db=MagicMock(), telegram_id="1", user_message="سلام")


def test_answer_missing_api_key_raises():
    service = ChatAssistantService()
    service.settings = MagicMock()
    service.settings.CHAT_ASSISTANT_ENABLED = True
    # No providers configured → not_configured (replaces legacy API_KEY check).
    service.router = MagicMock()
    service.router.providers.return_value = []
    with pytest.raises(ChatAssistantError, match="not_configured"):
        service.answer(db=MagicMock(), telegram_id="1", user_message="سلام")


def test_answer_empty_message_raises():
    service = ChatAssistantService()
    service.settings = MagicMock()
    service.settings.CHAT_ASSISTANT_ENABLED = True
    service.router = MagicMock()
    service.router.providers.return_value = [object()]
    with pytest.raises(ChatAssistantError, match="empty_message"):
        service.answer(db=MagicMock(), telegram_id="1", user_message="   ")


def test_rate_limit_blocks_after_threshold():
    service = ChatAssistantService()
    service.settings = MagicMock()
    service.settings.CHAT_ASSISTANT_MAX_MESSAGES_PER_HOUR = 2
    service._check_rate_limit("42")
    service._check_rate_limit("42")
    with pytest.raises(ChatAssistantError, match="تعداد پیام"):
        service._check_rate_limit("42")


def test_rate_limit_is_per_user():
    service = ChatAssistantService()
    service.settings = MagicMock()
    service.settings.CHAT_ASSISTANT_MAX_MESSAGES_PER_HOUR = 1
    service._check_rate_limit("42")
    service._check_rate_limit("99")


def test_catalog_context_handles_empty_catalog():
    service = ChatAssistantService()
    service.course_service = MagicMock()
    service.course_service.get_courses.return_value = []
    service.online_course_service = MagicMock()
    service.online_course_service.get_active_courses.return_value = []

    context = service._catalog_context(db=MagicMock())

    assert "فعلاً دوره دیجیتالی فعالی نیست" in context
    assert "فعلاً کلاس آنلاینی تعریف نشده است" in context


def test_system_prompt_forbids_payment_and_admin_disclosure():
    assert "اطلاعات پرداخت" in SYSTEM_PROMPT_FA or "پرداخت" in SYSTEM_PROMPT_FA
    assert "محرمانه" in SYSTEM_PROMPT_FA
    assert "پشتیبانی" in SYSTEM_PROMPT_FA


def test_bot_guide_mentions_support_as_escalation_path():
    assert "پشتیبانی" in BOT_GUIDE_FA


def test_question_guidance_prioritizes_catalog_for_purchase_questions():
    assert "کاتالوگ فعلی" in _question_guidance("قیمت دوره چقدر است؟")


def test_question_guidance_structures_troubleshooting_questions():
    assert "تشخیص علت" in _question_guidance("این خطا چرا رخ می‌دهد؟")
