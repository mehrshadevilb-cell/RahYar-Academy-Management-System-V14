"""Runtime patch: harden AIProviderRouter against HTTP 404 and prefer healthy models."""
from __future__ import annotations

import time
import urllib.error
from typing import Any

from src.ai import provider_router as pr

STALE = frozenset({"mimo-v2.5-free", "mimo-v2.5", "mimo-v2"})
NOT_FOUND_COOLDOWN = 3600


def _mark_not_found(router: pr.AIProviderRouter, provider_name: str, model: str) -> None:
    key = f"{provider_name}:{model}"
    router._model_cooldown_until[key] = time.time() + NOT_FOUND_COOLDOWN


def _ordered_candidates(self: pr.AIProviderRouter, providers: list) -> list:
    now = time.time()
    ready = []
    cooling = []
    for provider in providers:
        for model in provider.models:
            if (model or "").strip().lower() in STALE:
                _mark_not_found(self, provider.name, model)
                continue
            key = f"{provider.name}:{model}"
            blocked = max(
                self._cooldown_until.get(provider.name, 0.0),
                self._model_cooldown_until.get(key, 0.0),
            )
            item = (provider, model)
            if blocked > now:
                cooling.append(item)
            else:
                ready.append(item)

    def score(item):
        provider, model = item
        return (0 if self._is_free_model(model) else 1, provider.priority, model)

    ready.sort(key=score)
    if ready:
        return ready
    cooling.sort(key=score)
    return cooling


def _chat(self: pr.AIProviderRouter, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    providers = self.providers()
    timeout_seconds = kwargs.pop("timeout_seconds", None)
    if timeout_seconds is None:
        timeout_seconds = self.settings.AI_AGENT_TIMEOUT_SECONDS
    try:
        timeout_seconds = max(5, min(int(timeout_seconds), 120))
    except (TypeError, ValueError):
        timeout_seconds = min(max(self.settings.AI_AGENT_TIMEOUT_SECONDS, 5), 120)
    last: pr.AIProviderError | None = None
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
        provider_until = self._cooldown_until.get(provider.name, 0)
        model_until = self._model_cooldown_until.get(model_key, 0)
        blocked_until = max(provider_until, model_until)
        if blocked_until > now:
            skipped_until.append(blocked_until)
            continue
        attempted += 1
        request_kwargs = dict(kwargs)
        try:
            data = self._request(provider, model, messages, request_kwargs, timeout_seconds)
            self._model_cooldown_until.pop(model_key, None)
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
            if exc.code == 404 or (
                exc.code in {400, 404}
                and any(x in lowered for x in ("not found", "model", "does not exist", "unknown model", "invalid model"))
            ) or (exc.code == 400 and not body):
                _mark_not_found(self, provider.name, model)
                last = pr.AIProviderError(
                    f"model not found: {provider.name}/{model} (HTTP {exc.code})",
                    retryable=True,
                    retry_after=NOT_FOUND_COOLDOWN,
                    provider=provider.name,
                )
                continue
            if self._is_rate_limited(exc.code, body):
                cooldown = min(retry_after or 300, 86400)
                self._model_cooldown_until[model_key] = time.time() + cooldown
                last = pr.AIProviderError(
                    f"model rate limited: {provider.name}/{model}",
                    retryable=True,
                    retry_after=cooldown,
                    provider=provider.name,
                )
                continue
            if exc.code in {401, 403}:
                self._model_cooldown_until[model_key] = time.time() + 120
                last = pr.AIProviderError(
                    f"provider authentication failed: {provider.name}/{model}",
                    retryable=True,
                    retry_after=120,
                    provider=provider.name,
                )
                continue
            last = pr.AIProviderError(
                f"provider request failed: {provider.name}/{model} (HTTP {exc.code})",
                retryable=exc.code >= 500 or exc.code in {408, 409, 425, 429},
                retry_after=60 if exc.code >= 500 else (retry_after or 0),
                provider=provider.name,
            )
            if exc.code >= 500:
                used = transient_attempts.get(model_key, 0)
                if used < transient_retries:
                    transient_attempts[model_key] = used + 1
                    candidates.append((provider, model))
                else:
                    self._model_cooldown_until[model_key] = time.time() + 60
            continue
        except (urllib.error.URLError, TimeoutError, OSError):
            last = pr.AIProviderError(
                f"provider unavailable: {provider.name}/{model}",
                retryable=True,
                retry_after=30,
                provider=provider.name,
            )
            self._model_cooldown_until[model_key] = time.time() + 30
            continue
        except pr.AIProviderError as exc:
            last = exc
            self._model_cooldown_until[model_key] = time.time() + (exc.retry_after or 30)
            continue
    if last:
        raise last
    if skipped_until and attempted == 0:
        retry_after = max(1, int(round(min(skipped_until) - time.time())))
        raise pr.AIProviderError(
            f"All configured AI models are cooling down; retry in {retry_after}s",
            retryable=True,
            retry_after=retry_after,
        )
    raise pr.AIProviderError("All configured AI models are temporarily unavailable", retryable=True, retry_after=30)


def apply() -> None:
    pr.AIProviderRouter._ordered_candidates = _ordered_candidates  # type: ignore[method-assign]
    pr.AIProviderRouter.chat = _chat  # type: ignore[method-assign]


apply()
