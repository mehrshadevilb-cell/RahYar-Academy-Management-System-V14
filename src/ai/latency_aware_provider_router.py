from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from src.ai.provider_router import AIProvider, AIProviderRouter


class LatencyAwareAIProviderRouter(AIProviderRouter):
    """Live provider pool that learns health and latency and prefers the fastest healthy route."""

    def __init__(self) -> None:
        super().__init__()
        self._latency_ms: dict[str, float] = {}
        self._latency_samples: dict[str, int] = {}
        self._last_success: dict[str, float] = {}

    @staticmethod
    def _key(provider: AIProvider, model: str) -> str:
        return f"{provider.name}:{model}"

    @staticmethod
    def _healthy_success_age(last_success: float, now: float) -> int:
        return 0 if last_success and now - last_success <= 300 else 1

    def _record_latency(self, provider: AIProvider, model: str, elapsed_ms: float) -> None:
        key = self._key(provider, model)
        previous = self._latency_ms.get(key)
        # EWMA: recent network/provider conditions dominate old observations.
        self._latency_ms[key] = elapsed_ms if previous is None else (previous * 0.35 + elapsed_ms * 0.65)
        self._latency_samples[key] = self._latency_samples.get(key, 0) + 1
        self._last_success[key] = time.time()

    def providers(self) -> list[AIProvider]:
        providers = super().providers()
        adjusted: list[AIProvider] = []
        for provider in providers:
            model = provider.model
            key = self._key(provider, model)
            latency = self._latency_ms.get(key)
            if latency is None:
                adjusted.append(provider)
            else:
                adjusted.append(replace(provider, priority=min(9999, int(latency))))
        return adjusted

    def _ordered_candidates(self, providers: list[AIProvider]) -> list[tuple[AIProvider, str]]:
        candidates = [(provider, model) for provider in providers for model in provider.models]
        now = time.time()

        def score(item: tuple[AIProvider, str]) -> tuple[int, float, int, int, str]:
            provider, model = item
            key = self._key(provider, model)
            latency = self._latency_ms.get(key)
            # A live measured route wins. Among live routes, lowest latency wins.
            # Free is a tie-breaker, so a working fast provider is not held back
            # just because another free provider is slower.
            measured = 0 if latency is not None else 1
            observed_latency = latency if latency is not None else 10_000.0
            stale_penalty = self._healthy_success_age(self._last_success.get(key, 0.0), now)
            return (measured, observed_latency, stale_penalty, provider.priority, model)

        candidates.sort(key=score)
        return candidates

    def _test_request(self, provider: AIProvider, model: str, timeout: int) -> tuple[int, int, str]:
        started = time.perf_counter()
        result = super()._test_request(provider, model, timeout)
        elapsed = (time.perf_counter() - started) * 1000
        self._record_latency(provider, model, elapsed)
        return result

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        started = time.perf_counter()
        data = super().chat(messages, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        provider = str(data.get("_rahyar_provider") or "")
        model = str(data.get("_rahyar_model") or "")
        if provider and model:
            self._record_latency(
                AIProvider(name=provider, api_key="", base_url="", models=(model,)),
                model,
                elapsed,
            )
        return data

    def latency_snapshot(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, latency in self._latency_ms.items():
            provider, _, model = key.partition(":")
            rows.append(
                {
                    "provider": provider,
                    "model": model,
                    "latency_ms": round(latency),
                    "samples": self._latency_samples.get(key, 0),
                    "last_success": self._last_success.get(key, 0),
                }
            )
        return sorted(rows, key=lambda row: (row["latency_ms"], row["provider"], row["model"]))
