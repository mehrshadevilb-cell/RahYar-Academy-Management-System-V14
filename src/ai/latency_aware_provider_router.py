from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from src.ai.provider_router import AIProvider, AIProviderRouter


class LatencyAwareAIProviderRouter(AIProviderRouter):
    """Free-first router that learns recent model latency and prefers faster healthy routes."""

    def __init__(self) -> None:
        super().__init__()
        self._latency_ms: dict[str, float] = {}
        self._latency_samples: dict[str, int] = {}
        self._last_success: dict[str, float] = {}
        self._preferred: tuple[str, str] | None = None

    @staticmethod
    def _key(provider: AIProvider | str, model: str) -> str:
        name = provider if isinstance(provider, str) else provider.name
        return f"{name}:{model}"

    def record_probe_latency(self, provider_name: str, model: str, latency_ms: float) -> None:
        key = self._key(provider_name, model)
        previous = self._latency_ms.get(key)
        self._latency_ms[key] = float(latency_ms) if previous is None else (previous * 0.35 + float(latency_ms) * 0.65)
        self._latency_samples[key] = self._latency_samples.get(key, 0) + 1
        self._last_success[key] = time.time()
        self._preferred = (provider_name, model)

    def prefer_route(self, provider_name: str, model: str) -> None:
        self._preferred = (provider_name, model)

    def providers(self) -> list[AIProvider]:
        providers = super().providers()
        adjusted: list[AIProvider] = []
        for provider in providers:
            model = provider.model
            key = self._key(provider, model)
            latency = self._latency_ms.get(key)
            if latency is None:
                adjusted.append(provider)
                continue
            latency_priority = min(9999, int(latency))
            adjusted.append(replace(provider, priority=latency_priority))
        return adjusted

    def _ordered_candidates(self, providers: list[AIProvider]) -> list[tuple[AIProvider, str]]:
        candidates = AIProviderRouter._ordered_candidates(self, providers)
        now = time.time()
        preferred = self._preferred

        def score(item: tuple[AIProvider, str]) -> tuple[int, int, int, float, int, str]:
            provider, model = item
            key = self._key(provider, model)
            latency = self._latency_ms.get(key)
            last_success = self._last_success.get(key, 0.0)
            stale_penalty = 0 if last_success and now - last_success <= 300 else 1
            preferred_boost = 0
            if preferred and preferred[0] == provider.name and preferred[1] == model:
                preferred_boost = -1
            return (
                0 if self._is_free_model(model) else 1,
                preferred_boost,
                stale_penalty,
                latency if latency is not None else 10_000.0,
                provider.priority,
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
            self._preferred = (provider, model)
        return data

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
                "preferred": self._preferred == (provider, model),
            })
        return sorted(rows, key=lambda row: (row["latency_ms"], row["provider"], row["model"]))
