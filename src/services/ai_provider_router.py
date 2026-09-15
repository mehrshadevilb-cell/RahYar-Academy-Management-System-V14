from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from threading import Lock
from typing import Any
from urllib.parse import urlparse

from src.core.config.settings import get_settings, normalize_openai_compatible_base_url


@dataclass(frozen=True)
class AIProvider:
    name: str
    api_key: str
    base_url: str
    model: str
    priority: int = 100


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, retry_after: int | None = None, provider: str = "") -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.provider = provider


class AIProviderRouter:
    """Central OpenAI-compatible provider pool with per-provider cooldown.

    Providers are configured through AI_PROVIDERS_JSON. A legacy single-provider
    configuration remains a valid fallback. No API key is ever included in
    exceptions or status output.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._lock = Lock()
        self._cooldown_until: dict[str, float] = {}
        self._last_error: dict[str, str] = {}
        self._providers = self._load_providers()

    def _load_providers(self) -> list[AIProvider]:
        raw = (self.settings.AI_PROVIDERS_JSON or "").strip()
        providers: list[AIProvider] = []
        if raw:
            try:
                data = json.loads(raw)
                if not isinstance(data, list):
                    raise ValueError("AI_PROVIDERS_JSON must be a JSON array")
                for i, item in enumerate(data):
                    if not isinstance(item, dict):
                        continue
                    key_env = str(item.get("api_key_env", "")).strip()
                    import os
                    key = os.getenv(key_env, "").strip() if key_env else str(item.get("api_key", "")).strip()
                    base = normalize_openai_compatible_base_url(str(item.get("base_url", "")))
                    model = str(item.get("model", "")).strip()
                    name = str(item.get("name", f"provider-{i + 1}")).strip()
                    if key and base and model:
                        providers.append(AIProvider(name, key, base, model, int(item.get("priority", 100))))
            except (ValueError, TypeError, json.JSONDecodeError):
                self._last_error["config"] = "invalid AI_PROVIDERS_JSON"

        if not providers:
            key = self.settings.effective_ai_api_key
            if key:
                providers.append(AIProvider("primary", key, self.settings.effective_ai_base_url, self.settings.effective_ai_model, 100))
        return sorted(providers, key=lambda p: p.priority)

    @staticmethod
    def _retry_after(exc: urllib.error.HTTPError, body: str) -> int | None:
        value = exc.headers.get("Retry-After") if exc.headers else None
        if value:
            try:
                return max(1, min(int(float(value)), 86400))
            except ValueError:
                pass
        try:
            data = json.loads(body)
            value = data.get("error", {}).get("metadata", {}).get("retry_after_seconds")
            if value is not None:
                return max(1, min(int(value), 86400))
        except (ValueError, TypeError, AttributeError):
            pass
        return None

    @staticmethod
    def _headers(provider: AIProvider) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "RahYar-AIProviderRouter/1.0",
        }
        host = (urlparse(provider.base_url).hostname or "").lower()
        if host.endswith("agentrouter.org"):
            headers.update({"Originator": "codex_cli_rs", "Version": "0.101.0"})
        return headers

    def _available(self, provider: AIProvider) -> bool:
        return self._cooldown_until.get(provider.name, 0) <= time.time()

    def chat(self, messages: list[dict[str, Any]], *, max_tokens: int | None = None, temperature: float = 0.2, timeout: int | None = None) -> str:
        if not self._providers:
            raise AIProviderError("هیچ AI Provider فعالی پیکربندی نشده است.")
        last_error: AIProviderError | None = None
        attempted = 0
        for provider in self._providers:
            with self._lock:
                if not self._available(provider):
                    continue
            attempted += 1
            payload: dict[str, Any] = {"model": provider.model, "messages": messages, "temperature": temperature}
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            request = urllib.request.Request(
                provider.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=self._headers(provider), method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout or min(max(self.settings.AI_AGENT_TIMEOUT_SECONDS, 10), 180)) as response:
                    data = json.loads(response.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                with self._lock:
                    self._last_error.pop(provider.name, None)
                    self._cooldown_until.pop(provider.name, None)
                return str(content).strip()
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:1000]
                except Exception:
                    pass
                retry_after = self._retry_after(exc, body)
                # Fail over on rate limits, capacity errors, server errors and auth/config errors.
                if exc.code in {401, 403, 408, 409, 429} or exc.code >= 500:
                    cooldown = retry_after or (60 if exc.code >= 500 else 300)
                    with self._lock:
                        self._cooldown_until[provider.name] = time.time() + cooldown
                        self._last_error[provider.name] = f"HTTP {exc.code}; cooldown={cooldown}s"
                    last_error = AIProviderError(f"provider {provider.name} HTTP {exc.code}", retry_after=retry_after, provider=provider.name)
                    continue
                raise AIProviderError(f"provider {provider.name} HTTP {exc.code}", provider=provider.name) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                with self._lock:
                    self._cooldown_until[provider.name] = time.time() + 60
                    self._last_error[provider.name] = type(exc).__name__
                last_error = AIProviderError(f"provider {provider.name} unavailable", provider=provider.name)

        if attempted == 0:
            raise AIProviderError("همه Providerها موقتاً در Cooldown هستند.")
        if last_error:
            raise AIProviderError("همه AI Providerهای فعال ناموفق بودند.", retry_after=last_error.retry_after, provider=last_error.provider) from last_error
        raise AIProviderError("AI provider unavailable")

    def status(self) -> list[dict[str, Any]]:
        now = time.time()
        return [
            {"name": p.name, "model": p.model, "base_url": p.base_url, "priority": p.priority,
             "available": self._cooldown_until.get(p.name, 0) <= now,
             "cooldown_seconds": max(0, int(self._cooldown_until.get(p.name, 0) - now)),
             "last_error": self._last_error.get(p.name, "")}
            for p in self._providers
        ]


ai_provider_router = AIProviderRouter()
