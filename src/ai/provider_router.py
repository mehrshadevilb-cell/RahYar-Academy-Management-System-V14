from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from src.core.config.settings import get_settings


@dataclass(frozen=True)
class AIProvider:
    name: str
    api_key: str
    base_url: str
    models: tuple[str, ...]
    priority: int = 100
    enabled: bool = True

    @property
    def model(self) -> str:
        """Primary model (first in the list) for backward compatibility."""
        return self.models[0] if self.models else ""


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, retry_after: int = 0, provider: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = max(0, retry_after)
        self.provider = provider


class AIProviderRouter:
    """OpenAI-compatible provider pool with automatic failover.

    Configure AI_PROVIDERS_JSON as an array of provider objects. API keys should
    normally be referenced through api_key_env so secrets stay outside source.

    Each provider may declare either a single ``model`` (string) or multiple
    ``models`` (array). Models are tried in order before moving to the next
    provider.

    Example with multiple models per provider::

        [
          {
            "name": "agentrouter",
            "api_key_env": "AGENTROUTER_API_KEY",
            "base_url": "https://agentrouter.org/v1",
            "models": ["model-a", "model-b", "model-c"],
            "priority": 10
          },
          {
            "name": "orcarouter",
            "api_key_env": "ORCA_API_KEY",
            "base_url": "https://api.orcarouter.ai/v1",
            "model": "deepseek/deepseek-v4-flash-free",
            "priority": 20
          }
        ]

    The legacy AI_API_KEY/AI_BASE_URL/AI_MODEL configuration remains a single
    implicit provider when AI_PROVIDERS_JSON is empty.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._cooldown_until: dict[str, float] = {}

    def _parse(self) -> list[AIProvider]:
        raw = (self.settings.AI_PROVIDERS_JSON or "").strip()
        providers: list[AIProvider] = []
        if raw:
            try:
                rows = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise AIProviderError("AI_PROVIDERS_JSON is invalid JSON") from exc
            if not isinstance(rows, list):
                raise AIProviderError("AI_PROVIDERS_JSON must be a JSON array")
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or row.get("enabled", True) is False:
                    continue
                key = str(row.get("api_key", "") or "")
                key_env = str(row.get("api_key_env", "") or "")
                if key_env:
                    key = os.getenv(key_env, "")
                base_url = str(row.get("base_url", "") or "").strip().rstrip("/")
                name = str(row.get("name", f"provider-{index + 1}") or f"provider-{index + 1}")

                models: list[str] = []
                raw_models = row.get("models")
                if isinstance(raw_models, list):
                    models = [str(m).strip() for m in raw_models if str(m).strip()]
                else:
                    single = str(row.get("model", "") or "").strip()
                    if single:
                        models = [single]

                if key and base_url and models:
                    providers.append(
                        AIProvider(
                            name=name,
                            api_key=key,
                            base_url=base_url,
                            models=tuple(models),
                            priority=int(row.get("priority", 100)),
                        )
                    )
        if not providers and self.settings.effective_ai_api_key:
            providers.append(
                AIProvider(
                    name="primary",
                    api_key=self.settings.effective_ai_api_key,
                    base_url=self.settings.effective_ai_base_url,
                    models=(self.settings.effective_ai_model,),
                    priority=100,
                )
            )
        return sorted(providers, key=lambda p: p.priority)

    def providers(self) -> list[AIProvider]:
        return self._parse()

    def _headers(self, provider: AIProvider) -> dict[str, str]:
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

    @staticmethod
    def _retry_after(headers: Any, body: str) -> int:
        value = headers.get("Retry-After") or headers.get("retry-after")
        try:
            if value is not None:
                return max(1, int(float(value)))
        except (TypeError, ValueError):
            pass
        try:
            data = json.loads(body)
            value = data.get("error", {}).get("metadata", {}).get("retry_after_seconds", 0)
            return max(1, int(float(value))) if value else 0
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0

    @staticmethod
    def _is_rate_limited(code: int, body: str) -> bool:
        if code == 429:
            return True
        lowered = body.lower()
        return code in {402, 403} and ("rate" in lowered or "capacity" in lowered or "quota" in lowered)

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        providers = self.providers()
        if not providers:
            raise AIProviderError("No AI provider is configured")

        last: AIProviderError | None = None

        for provider in providers:
            now = time.time()
            if self._cooldown_until.get(provider.name, 0) > now:
                continue

            provider_rate_limited = False
            max_retry_after = 0

            for model in provider.models:
                payload = {"model": model, "messages": messages, **kwargs}
                request = urllib.request.Request(
                    provider.base_url.rstrip("/") + "/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=self._headers(provider),
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(
                        request,
                        timeout=min(max(self.settings.AI_AGENT_TIMEOUT_SECONDS, 5), 180),
                    ) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    if not isinstance(data, dict):
                        raise AIProviderError(
                            f"Invalid AI provider response: {provider.name}/{model}",
                            provider=provider.name,
                        )
                    data["_rahyar_provider"] = provider.name
                    data["_rahyar_model"] = model
                    return data
                except urllib.error.HTTPError as exc:
                    body = ""
                    try:
                        body = exc.read().decode("utf-8", errors="replace")[:1000]
                    except Exception:
                        pass
                    retry_after = self._retry_after(exc.headers, body)
                    if self._is_rate_limited(exc.code, body):
                        provider_rate_limited = True
                        max_retry_after = max(max_retry_after, retry_after or 300)
                        last = AIProviderError(
                            f"model rate limited: {provider.name}/{model}",
                            retryable=True,
                            retry_after=retry_after or 300,
                            provider=provider.name,
                        )
                        continue  # try next model of same provider
                    last = AIProviderError(
                        f"provider HTTP {exc.code}: {provider.name}/{model}",
                        provider=provider.name,
                    )
                    continue  # try next model
                except (urllib.error.URLError, TimeoutError):
                    last = AIProviderError(
                        f"provider unavailable: {provider.name}/{model}",
                        retryable=True,
                        provider=provider.name,
                    )
                    continue
                except (json.JSONDecodeError, ValueError, TypeError):
                    last = AIProviderError(
                        f"provider returned invalid response: {provider.name}/{model}",
                        provider=provider.name,
                    )
                    continue

            # All models of this provider failed
            if provider_rate_limited:
                cooldown = max_retry_after or 300
                self._cooldown_until[provider.name] = time.time() + min(cooldown, 86400)
                last = AIProviderError(
                    f"provider rate limited: {provider.name}",
                    retryable=True,
                    retry_after=cooldown,
                    provider=provider.name,
                )

        raise last or AIProviderError("All configured AI providers are cooling down", retryable=True)

    def status(self) -> list[dict[str, Any]]:
        now = time.time()
        return [
            {
                "name": p.name,
                "models": list(p.models),
                "model": p.model,
                "priority": p.priority,
                "cooldown_seconds": max(0, int(self._cooldown_until.get(p.name, 0) - now)),
            }
            for p in self.providers()
        ]
