import time

from src.core.config.settings import get_settings
from src.services.ai_agent_auto_fix import AIAgentAutoFixService


def test_auto_fix_disabled_by_default():
    service = AIAgentAutoFixService()
    # Default settings should reject unless env enables the flag.
    decision = service.evaluate(RuntimeError("boom"))
    if not get_settings().AI_AGENT_AUTO_FIX_ON_ERROR:
        assert decision.accepted is False
        assert "disabled" in decision.reason


def test_fingerprint_groups_volatile_ids():
    service = AIAgentAutoFixService()
    a = service._fingerprint(RuntimeError("user 123 failed"))
    b = service._fingerprint(RuntimeError("user 999 failed"))
    assert a == b


def test_cooldown_blocks_duplicate_fingerprint(monkeypatch):
    service = AIAgentAutoFixService()
    monkeypatch.setattr(service.settings, "AI_AGENT_AUTO_FIX_ON_ERROR", True)
    monkeypatch.setattr(service.settings, "AI_AGENT_ENABLED", True)
    first = service.evaluate(ValueError("handler crashed"))
    assert first.accepted is True
    service._recent[first.fingerprint] = time.time()
    second = service.evaluate(ValueError("handler crashed"))
    assert second.accepted is False
    assert "cooldown" in second.reason


def test_skips_telegram_conflict(monkeypatch):
    from aiogram.exceptions import TelegramConflictError

    service = AIAgentAutoFixService()
    monkeypatch.setattr(service.settings, "AI_AGENT_AUTO_FIX_ON_ERROR", True)
    monkeypatch.setattr(service.settings, "AI_AGENT_ENABLED", True)
    decision = service.evaluate(TelegramConflictError(method="getUpdates", message="conflict"))
    assert decision.accepted is False
