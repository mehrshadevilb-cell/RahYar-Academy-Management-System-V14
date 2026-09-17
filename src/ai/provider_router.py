from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

from src.core.config.settings import get_settings, normalize_openai_compatible_base_url


@dataclass(frozen=True)
class AIProvider:
    name: str
    api_key: str
    base_url: str
    models: tuple[str, ...]
    priority: int = 100
    enabled: bool = True
    provider_type: str = "openai_compatible"

    @property
    def model(self) -> str:
        return self.models[0] if self.models else ""


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, retry_after: int = 0, provider: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = max(0, retry_after)
        self.provider = provider


class AIProviderRouter:
    """AI provider pool with DB/env discovery and model-level failover."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._cooldown_until: dict[str, float] = {}
        self._model_cooldown_until: dict[str, float] = {}

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        return normalize_openai_compatible_base_url((value or "").strip())

    @staticmethod
    def _infer_provider_type(name: str, base_url: str) -> str:
        host = (urlparse(base_url).hostname or "").lower()
        lowered = f"{name} {host}".lower()
        if "generativelanguage.googleapis.com" in lowered or "google" in lowered or "gemini" in lowered:
            return "google"
        if "anthropic" in lowered or "claude" in lowered:
            return "anthropic"
        return "openai_compatible"

    @staticmethod
    def _is_free_model(model: Any) -> bool:
        if isinstance(model, str):
            model_id = model.lower()
            return model_id.endswith(":free") or "-free" in model_id
        model_id = str(getattr(model, "model_id", "") or "").lower()
        if model_id.endswith(":free") or "-free" in model_id:
            return True
        raw = getattr(model, "raw_metadata", None) or {}
        pricing = raw.get("pricing") if isinstance(raw, dict) else None
        if isinstance(pricing, dict):
            try:
                return float(pricing.get("prompt", pricing.get("input", 1))) == 0.0 and float(pricing.get("completion", pricing.get("output", 1))) == 0.0
            except (TypeError, ValueError):
                pass
        return False

    @classmethod
    def _provider_from_env(cls, name: str, key_var: str, url_var: str, model_var: str, priority: int) -> AIProvider | None:
        key = (os.getenv(key_var) or "").strip()
        base_url = cls._normalize_base_url(os.getenv(url_var) or "")
        model = (os.getenv(model_var) or "").strip()
        if not (key and base_url):
            return None
        return AIProvider(name=name, api_key=key, base_url=base_url, models=(model,) if model else (), priority=priority, provider_type=cls._infer_provider_type(name, base_url))

    @classmethod
    def _catalog_provider(cls, name: str, key_var: str, url_var: str, priority: int) -> AIProvider | None:
        key = (os.getenv(key_var) or "").strip()
        base_url = cls._normalize_base_url(os.getenv(url_var) or "")
        if not (key and base_url):
            return None
        return AIProvider(name=name, api_key=key, base_url=base_url, models=(), priority=priority, provider_type=cls._infer_provider_type(name, base_url))

    def _discover_models(self, provider: AIProvider, timeout: int = 12) -> AIProvider:
        if provider.provider_type != "openai_compatible":
            return provider
        url = provider.base_url.rstrip("/") + "/models"
        request = urllib.request.Request(url, headers=self._headers(provider), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            rows = data.get("data", []) if isinstance(data, dict) else []
            models = []
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        model_id = str(row.get("id") or row.get("name") or "").strip()
                        if model_id and model_id not in models:
                            models.append(model_id)
            if models:
                return AIProvider(name=provider.name, api_key=provider.api_key, base_url=provider.base_url, models=tuple(models), priority=provider.priority, enabled=provider.enabled, provider_type=provider.provider_type)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return provider

    def _from_database(self) -> list[AIProvider]:
        try:
            from src.database.models.ai_provider import AIProvider as DBProvider
            from src.database.session import SessionLocal
            from src.services.ai.credential_crypto import decrypt_api_key
            db = SessionLocal()
            try:
                result = []
                rows = db.query(DBProvider).filter(DBProvider.is_active.is_(True)).all()
                for index, provider in enumerate(rows):
                    active_models = [m for m in provider.models if m.is_active]
                    if not active_models:
                        continue
                    active_models.sort(key=lambda m: (not self._is_free_model(m), not m.is_default, -(m.context_window or 0), m.model_id))
                    try:
                        key = decrypt_api_key(provider.api_key_encrypted)
                    except Exception:
                        continue
                    result.append(AIProvider(name=provider.name, api_key=key, base_url=self._normalize_base_url(provider.base_url), models=tuple(m.model_id for m in active_models), priority=index, provider_type=provider.provider_type or self._infer_provider_type(provider.name, provider.base_url)))
                return result
            finally:
                db.close()
        except Exception:
            return []

    def _env_providers(self) -> list[AIProvider]:
        providers: list[AIProvider] = []
        agentrouter_key = (os.getenv("AGENTROUTER_API_KEY") or "").strip()
        agentrouter_model = (os.getenv("AI_MODEL") or os.getenv("AI_AGENT_MODEL") or "").strip()
        if agentrouter_key:
            providers.append(AIProvider(name="agentrouter", api_key=agentrouter_key, base_url=self._normalize_base_url(os.getenv("AI_BASE_URL") or "https://agentrouter.org/v1"), models=(agentrouter_model,) if agentrouter_model else (), priority=0))

        primary = self._provider_from_env("primary", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL", 10)
        if primary:
            providers.append(primary)
        secondary = self._provider_from_env("secondary", "AI2_API_KEY", "AI2_BASE_URL", "AI2_MODEL", 20)
        if secondary:
            providers.append(secondary)

        # OpenCode Zen and OpenAI are model-catalog providers. Their keys and
        # base URLs come from ENV; model IDs are discovered from /models so no
        # stale model list has to be committed to the repository.
        opencode = self._catalog_provider("opencode-zen", "OPENCODE_API_KEY", "OPENCODE_ZEN_BASE_URL", 30)
        if opencode:
            providers.append(self._discover_models(opencode))
        openai = self._catalog_provider("openai", "OPENAI_API_KEY", "OPENAI_BASE_URL", 40)
        if openai:
            providers.append(self._discover_models(openai))
        return providers

    @staticmethod
    def _merge_providers(providers: list[AIProvider]) -> list[AIProvider]:
        merged: dict[tuple[str, str, str], AIProvider] = {}
        for provider in providers:
            for model in provider.models:
                key = (provider.name.lower(), provider.base_url.rstrip("/"), model)
                current = merged.get(key)
                if current is None or provider.priority < current.priority:
                    merged[key] = AIProvider(name=provider.name, api_key=provider.api_key, base_url=provider.base_url, models=(model,), priority=provider.priority, enabled=provider.enabled, provider_type=provider.provider_type)
        return sorted(merged.values(), key=lambda p: (not self._is_free_model(p.model), p.priority, p.name, p.model))

    def _parse(self) -> list[AIProvider]:
        db_providers = self._from_database()
        raw = (self.settings.AI_PROVIDERS_JSON or "").strip()
        configured: list[AIProvider] = []
        if raw:
            rows = json.loads(raw)
            if not isinstance(rows, list):
                raise AIProviderError("AI_PROVIDERS_JSON must be a JSON array")
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or row.get("enabled", True) is False:
                    continue
                key = str(row.get("api_key", "") or "")
                key_env = str(row.get("api_key_env", "") or "")
                if key_env:
                    key = os.getenv(key_env, "")
                base_url = self._normalize_base_url(str(row.get("base_url", "") or ""))
                name = str(row.get("name", f"provider-{index + 1}") or f"provider-{index + 1}")
                models = [str(m).strip() for m in row.get("models", []) if str(m).strip()] if isinstance(row.get("models"), list) else []
                if not models:
                    single = str(row.get("model", "") or "").strip()
                    if single:
                        models = [single]
                if key and base_url:
                    provider = AIProvider(name=name, api_key=key, base_url=base_url, models=tuple(models), priority=int(row.get("priority", 100)), provider_type=str(row.get("provider_type", "") or self._infer_provider_type(name, base_url)))
                    configured.append(self._discover_models(provider) if not models else provider)
        candidates = configured + db_providers + self._env_providers()
        if not candidates:
            raise AIProviderError("No AI provider is configured")
        return self._merge_providers(candidates)

    def providers(self) -> list[AIProvider]:
        return self._parse()

    def reset_cooldowns(self) -> None:
        self._cooldown_until.clear()
        self._model_cooldown_until.clear()

    def cooldown_snapshot(self) -> dict[str, int]:
        now = time.time()
        return {key: max(0, int(round(until - now))) for key, until in self._model_cooldown_until.items() if until > now}

    def _headers(self, provider: AIProvider) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "RahYar-AIProviderRouter/1.6"}
        if (urlparse(provider.base_url).hostname or "").lower().endswith("agentrouter.org"):
            headers.update({"Originator": "codex_cli_rs", "Version": "0.101.0"})
        return headers

    @staticmethod
    def _extract_text(data: Any, provider_type: str) -> str:
        if provider_type == "google":
            return " ".join(str(part.get("text", "")) for candidate in data.get("candidates", []) if isinstance(candidate, dict) for part in candidate.get("content", {}).get("parts", []) if isinstance(part, dict)).strip() if isinstance(data, dict) else ""
        if provider_type == "anthropic":
            return " ".join(str(part.get("text", "")) for part in data.get("content", []) if isinstance(part, dict)).strip() if isinstance(data, dict) else ""
        choices = data.get("choices", []) if isinstance(data, dict) else []
        if not choices or not isinstance(choices[0], dict):
            return ""
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict)).strip()
        return str(content).strip() if content else ""

    def _request(self, provider: AIProvider, model: str, messages: list[dict[str, Any]], kwargs: dict[str, Any], timeout: int) -> dict[str, Any]:
        payload = {"model": model, "messages": messages, **kwargs}
        url = provider.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=self._headers(provider), method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict) or not self._extract_text(data, provider.provider_type):
            raise AIProviderError(f"AI provider returned an empty response: {provider.name}/{model}", retryable=True, retry_after=30, provider=provider.name)
        return data

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        providers = self.providers()
        timeout = max(5, min(int(kwargs.pop("timeout_seconds", self.settings.AI_AGENT_TIMEOUT_SECONDS)), 120))
        last: AIProviderError | None = None
        now = time.time()
        candidates = [(p, p.model) for p in providers if p.model]
        for provider, model in candidates:
            key = f"{provider.name}:{model}"
            if max(self._cooldown_until.get(provider.name, 0), self._model_cooldown_until.get(key, 0)) > now:
                continue
            try:
                data = self._request(provider, model, messages, dict(kwargs), timeout)
                self._model_cooldown_until.pop(key, None)
                data.update(_rahyar_provider=provider.name, _rahyar_model=model, _rahyar_is_free=self._is_free_model(model))
                return data
            except urllib.error.HTTPError as exc:
                retry_after = 60
                if exc.code == 429:
                    self._model_cooldown_until[key] = time.time() + 300
                elif exc.code in {401, 403}:
                    self._model_cooldown_until[key] = time.time() + 30
                last = AIProviderError(f"provider request failed: {provider.name}/{model} (HTTP {exc.code})", retryable=exc.code >= 500, retry_after=retry_after, provider=provider.name)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                self._model_cooldown_until[key] = time.time() + 60
                last = AIProviderError(f"provider unavailable: {provider.name}/{model}", retryable=True, retry_after=60, provider=provider.name)
        if last:
            raise last
        raise AIProviderError("All configured AI models are currently unavailable", retryable=True, retry_after=60)
