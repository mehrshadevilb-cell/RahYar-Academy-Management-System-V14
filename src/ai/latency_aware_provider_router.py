from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from src.ai.provider_router import AIProvider, AIProviderRouter


class LatencyAwareAIProviderRouter(AIProviderRouter):
    """Route to the fastest recently healthy model and fail over on failure."""

    def __init__(self) -> None:
        super().__init__()
        self._latency_ms: dict[str, float] = {}
        self._latency_samples: dict[str, int] = {}
        self._last_success: dict[str, float] = {}

    def _headers(self, provider: AIProvider) -> dict[str, str]:
        headers = super()._headers(provider)
        host = (urlparse(provider.base_url).hostname or "").lower()
        if host.endswith("bytez.com"):
            headers["Authorization"] = provider.api_key
        return headers

    @staticmethod
    def _key(provider: AIProvider, model: str) -> str:
        return f"{provider.name}:{model}"

    def _ordered_candidates(self, providers: list[AIProvider]) -> list[tuple[AIProvider, str]]:
        candidates = [(provider, model) for provider in providers for model in provider.models]
        now = time.time()

        def score(item: tuple[AIProvider, str]) -> tuple[int, int, int, int, float, str]:
            provider, model = item
            key = self._key(provider, model)
            latency = self._latency_ms.get(key)
            last_success = self._last_success.get(key, 0.0)
            # Routing order is deterministic: free models first, then provider
            # priority, then model priority. Latency is only a tie-breaker and
            # must never cause a slower paid route to jump ahead of a free route.
            free_rank = 0 if self._is_free_model(model) else 1
            stale_penalty = 0 if last_success and now - last_success <= 300 else 1
            measured = 0 if latency is not None else 1
            return (
                free_rank,
                provider.priority,
                stale_penalty,
                measured,
                latency if latency is not None else 10_000.0,
                model,
            )

        candidates.sort(key=score)
        return candidates

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        started = time.perf_counter()
        data = super().chat(messages, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        provider = str(data.get("_rahyar_provider") or "")
        model = str(data.get("_rahyar_model") or "")
        if provider and model:
            key = f"{provider}:{model}"
            previous = self._latency_ms.get(key)
            self._latency_ms[key] = elapsed if previous is None else (previous * 0.35 + elapsed * 0.65)
            self._latency_samples[key] = self._latency_samples.get(key, 0) + 1
            self._last_success[key] = time.time()
        return data

    def record_health_latency(self, provider: str, model: str, latency_ms: float) -> None:
        key = f"{provider}:{model}"
        previous = self._latency_ms.get(key)
        self._latency_ms[key] = latency_ms if previous is None else (previous * 0.35 + latency_ms * 0.65)
        self._latency_samples[key] = self._latency_samples.get(key, 0) + 1
        self._last_success[key] = time.time()

    def latency_snapshot(self) -> list[dict[str, Any]]:
        rows = []
        for key, latency in self._latency_ms.items():
            provider, _, model = key.partition(":")
            rows.append({
                "provider": provider,
                "model": model,
                "latency_ms": round(latency),
                "samples": self._latency_samples.get(key, 0),
                "last_success": self._last_success.get(key, 0),
            })
        return sorted(rows, key=lambda row: (row["latency_ms"], row["provider"], row["model"]))
