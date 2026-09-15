import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.bot.middlewares.security import FLOOD_MAX_UPDATES, SecurityMiddleware


def test_flooding_allows_up_to_the_limit():
    middleware = SecurityMiddleware()
    for _ in range(FLOOD_MAX_UPDATES):
        assert middleware._is_flooding(telegram_id=1) is False


def test_flooding_blocks_after_the_limit():
    middleware = SecurityMiddleware()
    for _ in range(FLOOD_MAX_UPDATES):
        middleware._is_flooding(telegram_id=1)
    assert middleware._is_flooding(telegram_id=1) is True


def test_flooding_is_tracked_per_user():
    middleware = SecurityMiddleware()
    for _ in range(FLOOD_MAX_UPDATES):
        middleware._is_flooding(telegram_id=1)
    # A different user must not be penalized by user 1's flood.
    assert middleware._is_flooding(telegram_id=2) is False


def test_blocked_user_is_denied_and_handler_not_called():
    middleware = SecurityMiddleware()
    middleware._repository = MagicMock()
    middleware._repository.get_user_by_telegram_id.return_value = SimpleNamespace(is_active=False)

    handler_called = {"value": False}

    async def fake_handler(evt, data):
        handler_called["value"] = True
        return "should not reach here"

    async def fake_answer(*args, **kwargs):
        return None

    event = SimpleNamespace(from_user=SimpleNamespace(id=42), answer=fake_answer)

    result = asyncio.run(middleware(fake_handler, event, {"db": object()}))

    assert result is None
    assert handler_called["value"] is False


def test_active_user_reaches_handler():
    middleware = SecurityMiddleware()
    middleware._repository = MagicMock()
    middleware._repository.get_user_by_telegram_id.return_value = SimpleNamespace(is_active=True)

    event = SimpleNamespace(from_user=SimpleNamespace(id=42))

    async def fake_handler(evt, data):
        return "ok"

    result = asyncio.run(middleware(fake_handler, event, {"db": object()}))

    assert result == "ok"


def test_missing_from_user_passes_through_without_error():
    middleware = SecurityMiddleware()
    event = SimpleNamespace()  # no from_user attribute at all

    async def fake_handler(evt, data):
        return "ok"

    result = asyncio.run(middleware(fake_handler, event, {}))

    assert result == "ok"
