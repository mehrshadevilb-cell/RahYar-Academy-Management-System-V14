from __future__ import annotations

"""Single shared latency-aware router for Agent + Chat Assistant + AIClient.

Keeps free-first failover, latency learning, and (when Redis is available)
cross-process model cooldowns consistent across all AI entrypoints.
"""

from src.ai.latency_aware_provider_router import LatencyAwareAIProviderRouter

_shared: LatencyAwareAIProviderRouter | None = None


def get_shared_router() -> LatencyAwareAIProviderRouter:
    global _shared
    if _shared is None:
        _shared = LatencyAwareAIProviderRouter()
    return _shared


def reset_shared_router() -> None:
    """Test helper: drop the process-local singleton."""
    global _shared
    _shared = None
