import asyncio
from types import SimpleNamespace

import pytest

from src.bot.handlers import chat_assistant as handler
from src.services.chat_assistant_service import ChatAssistantError, ChatAssistantService


def test_feedback_is_limited_to_questions_and_help_requests():
    assert handler.should_show_feedback("سلام") is False
    assert handler.should_show_feedback("ممنون، خیلی خوب بود") is False
    assert handler.should_show_feedback("چطور وکال را تمیز میکس کنم؟") is True
    assert handler.should_show_feedback("راهنمای Plugin") is True


class FakeBot:
    async def send_chat_action(self, chat_id, action):
        self.last_action = (chat_id, action)


class FakeMessage:
    def __init__(self, text: str, telegram_id: int = 123):
        self.text = text
        self.chat = SimpleNamespace(id=telegram_id)
        self.from_user = SimpleNamespace(id=telegram_id)
        self.bot = FakeBot()
        self.sent: list[str] = []

    async def answer(self, text, **kwargs):
        self.sent.append(text)


@pytest.mark.asyncio
async def test_telegram_chat_handler_reaches_service(monkeypatch):
    message = FakeMessage("قیمت دوره چقدره؟")

    class FakeProfile:
        def get_profile(self, db, telegram_id):
            return object()

    class FakeAssistant:
        def answer(self, db, telegram_id, user_message):
            assert telegram_id == "123"
            assert user_message == "قیمت دوره چقدره؟"
            return "قیمت فعلی را از منوی دوره‌ها می‌توانید ببینید."

    monkeypatch.setattr(handler, "profile_service", FakeProfile())
    monkeypatch.setattr(handler, "chat_assistant_service", FakeAssistant())

    await handler.chat_fallback(message, db=object())

    assert message.sent == [
        "🤖 <b>راه‌یار</b>\n\nقیمت فعلی را از منوی دوره‌ها می‌توانید ببینید."
    ]
    assert message.bot.last_action == (123, "typing")


class FakeRedis:
    def __init__(self):
        self.values: dict[str, int] = {}

    def eval(self, script, keys, key, ttl):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]


def test_chat_rate_limit_is_shared_between_service_instances(monkeypatch):
    settings = SimpleNamespace(
        CHAT_ASSISTANT_ENABLED=True,
        CHAT_ASSISTANT_MAX_MESSAGES_PER_HOUR=2,
        REDIS_URL="redis://test",
    )
    shared_redis = FakeRedis()

    first = object.__new__(ChatAssistantService)
    first.settings = settings
    first._recent_messages = {}
    first._redis = shared_redis

    second = object.__new__(ChatAssistantService)
    second.settings = settings
    second._recent_messages = {}
    second._redis = shared_redis

    first._check_rate_limit("42")
    second._check_rate_limit("42")
    with pytest.raises(ChatAssistantError):
        first._check_rate_limit("42")
