from __future__ import annotations

"""Single shared latency-aware router for Agent + Chat Assistant + AIClient."""

import time
import urllib.error
from typing import Any

from src.ai.latency_aware_provider_router import LatencyAwareAIProviderRouter
from src.ai.provider_router import AIProvider, AIProviderError


class SharedSmartRouter(LatencyAwareAIProviderRouter):
    """Latency-aware router + 404 blacklist + Redis cooldowns + cooldown-aware ordering."""

    _STALE_MODEL_IDS = {"mimo-v2.5-free", "mimo-v2.5"}

    def __init__(self) -> None:
        super().__init__()
        self._redis = None
        self._init_redis_cooldown_store()

    def _is_stale_model_id(self, model: str) -> bool:
        return (model or "").strip().lower() in self._STALE_MODEL_IDS

    def _init_redis_cooldown_store(self) -> None:
        try:
            import redis
        except ImportError:
            return
        url = (self.settings.REDIS_URL or "").strip()
        if not url:
            return
        try:
            client = redis.Redis.from_url(
                url, decode_responses=True, socket_connect_timeout=1.5, socket_timeout=1.5
            )
            client.ping()
            self._redis = client
            now = time.time()
            for key in self._redis.scan_iter(match="rahyar:ai:model-cooldown:*", count=100):
                ttl = self._redis.ttl(key)
                if ttl and ttl > 0:
                    model_key = key.removeprefix("rahyar:ai:model-cooldown:")
                    self._model_cooldown_until[model_key] = now + float(ttl)
        except Exception:
            self._redis = None

    def _persist_model_cooldown(self, model_key: str, seconds: int) -> None:
        seconds = max(1, min(int(seconds), 86400))
        self._model_cooldown_until[model_key] = time.time() + seconds
        if self._redis is None:
            return
        try:
            self._redis.setex(f"rahyar:ai:model-cooldown:{model_key}", seconds, "1")
        except Exception:
            self._redis = None

    def _clear_model_cooldown(self, model_key: str) -> None:
        self._model_cooldown_until.pop(model_key, None)
        if self._redis is None:
            return
        try:
            self._redis.delete(f"rahyar:ai:model-cooldown:{model_key}")
        except Exception:
            self._redis = None

    def _ordered_candidates(self, providers: list[AIProvider]) -> list[tuple[AIProvider, str]]:
        now = time.time()
        candidates: list[tuple[AIProvider, str]] = []
        for provider in providers:
            for model in provider.models:
                if self._is_stale_model_id(model):
                    continue
                model_key = f"{provider.name}:{model}"
                if max(
                    self._cooldown_until.get(provider.name, 0),
                    self._model_cooldown_until.get(model_key, 0),
                ) > now:
                    continue
                candidates.append((provider, model))
        if not candidates:
            candidates = [
                (p, m) for p in providers for m in p.models if not self._is_stale_model_id(m)
            ]
        candidates.sort(
            key=lambda item: (not self._is_free_model(item[1]), item[0].priority, item[1])
        )
        return candidates

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        providers = self.providers()
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        if timeout_seconds is None:
            timeout_seconds = self.settings.AI_AGENT_TIMEOUT_SECONDS
        try:
            timeout_seconds = max(5, min(int(timeout_seconds), 120))
        except (TypeError, ValueError):
            timeout_seconds = 60
        last: AIProviderError | None = None
        candidates = self._ordered_candidates(providers)
        try:
            transient_retries = max(0, min(int(self.settings.AI_AGENT_MAX_RETRIES), 5))
        except (TypeError, ValueError):
            transient_retries = 2
        transient_attempts: dict[str, int] = {}
        now = time.time()
        skipped_until: list[float] = []
        attempted = 0
        for provider, model in candidates:
            model_key = f"{provider.name}:{model}"
            blocked_until = max(
                self._cooldown_until.get(provider.name, 0),
                self._model_cooldown_until.get(model_key, 0),
            )
            if blocked_until > now:
                skipped_until.append(blocked_until)
                continue
            attempted += 1
            request_kwargs = dict(kwargs)
            started = time.perf_counter()
            try:
                data = self._request(provider, model, messages, request_kwargs, timeout_seconds)
                self._clear_model_cooldown(model_key)
                elapsed = (time.perf_counter() - started) * 1000
                key = f"{provider.name}:{model}"
                previous = self._latency_ms.get(key)
                self._latency_ms[key] = (
                    elapsed if previous is None else (previous * 0.35 + elapsed * 0.65)
                )
                self._latency_samples[key] = self._latency_samples.get(key, 0) + 1
                self._last_success[key] = time.time()
                data["_rahyar_provider"] = provider.name
                data["_rahyar_model"] = model
                data["_rahyar_is_free"] = self._is_free_model(model)
                return data
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:1000]
                except Exception:
                    pass
                retry_after = self._retry_after(exc.headers, body)
                lowered = body.lower()
                if self._is_rate_limited(exc.code, body):
                    self._persist_model_cooldown(model_key, min(retry_after or 300, 86400))
                    last = AIProviderError(
                        f"model rate limited: {provider.name}/{model}",
                        retryable=True,
                        retry_after=retry_after or 30,
                        provider=provider.name,
                    )
                    continue
                if (
                    exc.code in {404, 400}
                    or "model_not_found" in lowered
                    or "does not exist" in lowered
                ):
                    self._persist_model_cooldown(model_key, 3600)
                    last = AIProviderError(
                        f"model unavailable (HTTP {exc.code}): {provider.name}/{model}",
                        retryable=True,
                        retry_after=0,
                        provider=provider.name,
                    )
                    continue
                if exc.code in {401, 403}:
                    self._persist_model_cooldown(model_key, 120)
                    last = AIProviderError(
                        f"auth/forbidden: {provider.name}/{model}",
                        retryable=True,
                        retry_after=120,
                        provider=provider.name,
                    )
                    continue
                last = AIProviderError(
                    f"provider request failed: {provider.name}/{model} (HTTP {exc.code})",
                    retryable=exc.code >= 500,
                    retry_after=60 if exc.code >= 500 else 0,
                    provider=provider.name,
                )
                if exc.code >= 500:
                    used = transient_attempts.get(model_key, 0)
                    if used < transient_retries:
                        transient_attempts[model_key] = used + 1
                        candidates.append((provider, model))
                    else:
                        self._persist_model_cooldown(model_key, 60)
                continue
            except (urllib.error.URLError, TimeoutError, OSError):
                last = AIProviderError(
                    f"provider unavailable: {provider.name}/{model}",
                    retryable=True,
                    retry_after=30,
                    provider=provider.name,
                )
                self._persist_model_cooldown(model_key, 30)
                continue
            except AIProviderError as exc:
                last = exc
                self._persist_model_cooldown(model_key, exc.retry_after or 30)
                continue
        if last:
            raise last
        if skipped_until and attempted == 0:
            retry_after = max(1, int(round(min(skipped_until) - time.time())))
            raise AIProviderError(
                f"All configured AI models are cooling down; retry in {retry_after}s",
                retryable=True,
                retry_after=retry_after,
            )
        raise AIProviderError(
            "All configured AI models are temporarily unavailable",
            retryable=True,
            retry_after=30,
        )


_shared: SharedSmartRouter | None = None


def get_shared_router() -> SharedSmartRouter:
    global _shared
    if _shared is None:
        _shared = SharedSmartRouter()
    return _shared


def reset_shared_router() -> None:
    global _shared
    _shared = None
