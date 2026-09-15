from __future__ import annotations

from src.ai.latency_aware_provider_router import LatencyAwareAIProviderRouter
from src.ai.provider_router import AIProvider


def _provider(name: str, model: str, priority: int = 100) -> AIProvider:
    return AIProvider(
        name=name,
        api_key="test",
        base_url="https://example.test/v1",
        models=(model,),
        priority=priority,
    )


def test_fastest_measured_provider_wins_over_slower_free_provider() -> None:
    router = LatencyAwareAIProviderRouter()
    slow_free = _provider("free-provider", "slow-free:free", 0)
    fast_paid = _provider("fast-provider", "fast-paid", 50)
    router._latency_ms["free-provider:slow-free:free"] = 1200.0
    router._latency_ms["fast-provider:fast-paid"] = 180.0
    router._last_success["free-provider:slow-free:free"] = 1.0
    router._last_success["fast-provider:fast-paid"] = 1.0

    ordered = router._ordered_candidates([slow_free, fast_paid])

    assert ordered[0] == (fast_paid, "fast-paid")


def test_unmeasured_provider_stays_available_as_fallback() -> None:
    router = LatencyAwareAIProviderRouter()
    measured = _provider("measured", "model-a")
    unmeasured = _provider("unmeasured", "model-b")
    router._latency_ms["measured:model-a"] = 250.0
    router._last_success["measured:model-a"] = 1.0

    ordered = router._ordered_candidates([unmeasured, measured])

    assert ordered[0] == (measured, "model-a")
    assert ordered[1] == (unmeasured, "model-b")
