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
        return self.models[0] if self.models else ""


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, retry_after: int = 0, provider: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = max(0, retry_after)
        self.provider = provider


class AIProviderRouter:
    """AI provider pool with DB discovery, global free-first routing and model failover."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._cooldown_until: dict[str, float] = {}
        self._model_cooldown_until: dict[str, float] = {}

    @staticmethod
    def _provider_from_env(name: str, key_var: str, url_var: str, model_var: str, priority: int) -> AIProvider | None:
        key = (os.getenv(key_var) or "").strip()
        base_url = (os.getenv(url_var) or "").strip().rstrip("/")
        model = (os.getenv(model_var) or "").strip()
        if not (key and base_url and model):
            return None
        return AIProvider(name=name, api_key=key, base_url=base_url, models=(model,), priority=priority)

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
            prompt = pricing.get("prompt", pricing.get("input"))
            completion = pricing.get("completion", pricing.get("output"))
            try:
                if prompt is not None and completion is not None:
                    return float(prompt) == 0.0 and float(completion) == 0.0
            except (TypeError, ValueError):
                pass
        try:
            return (
                getattr(model, "pricing_input", None) is not None
                and getattr(model, "pricing_output", None) is not None
                and float(model.pricing_input) == 0.0
                and float(model.pricing_output) == 0.0
            )
        except (TypeError, ValueError):
            return False

    def _from_database(self) -> list[AIProvider]:
        """Load active DB providers and order their models free-first."""
        try:
            from src.database.models.ai_model import AIModel
            from src.database.models.ai_provider import AIProvider as DBProvider
            from src.database.session import SessionLocal
            from src.services.ai.credential_crypto import decrypt_api_key

            db = SessionLocal()
            try:
                rows = db.query(DBProvider).filter(DBProvider.is_active.is_(True)).all()
                result: list[AIProvider] = []
                for index, provider in enumerate(rows):
                    active_models = [m for m in provider.models if m.is_active]
                    if not active_models:
                        continue
                    active_models.sort(
                        key=lambda m: (
                            not self._is_free_model(m),
                            not m.is_default,
                            -(m.context_window or 0),
                            m.model_id,
                        )
                    )
                    try:
                        api_key = decrypt_api_key(provider.api_key_encrypted)
                    except Exception:
                        continue
                    result.append(
                        AIProvider(
                            name=provider.name,
                            api_key=api_key,
                            base_url=provider.base_url.rstrip("/"),
                            models=tuple(m.model_id for m in active_models),
                            priority=index,
                        )
                    )
                return result
            finally:
                db.close()
        except Exception:
            return []

    def _parse(self) -> list[AIProvider]:
        db_providers = self._from_database()
        if db_providers:
            return db_providers

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
                    providers.append(AIProvider(name=name, api_key=key, base_url=base_url, models=tuple(models), priority=int(row.get("priority", 100))))

        if not providers:
            primary = self._provider_from_env("primary", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL", 10)
            if primary:
                providers.append(primary)
            secondary = self._provider_from_env("secondary", "AI2_API_KEY", "AI2_BASE_URL", "AI2_MODEL", 20)
            if secondary:
                providers.append(secondary)

        if not providers and self.settings.effective_ai_api_key:
            providers.append(AIProvider(name="primary", api_key=self.settings.effective_ai_api_key, base_url=self.settings.effective_ai_base_url, models=(self.settings.effective_ai_model,), priority=100))
        return sorted(providers, key=lambda p: p.priority)

    def providers(self) -> list[AIProvider]:
        return self._parse()

    def _headers(self, provider: AIProvider) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "RahYar-AIProviderRouter/1.0"}
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
        return code in {402, 403} and any(x in lowered for x in ("rate", "capacity", "quota", "limit"))

    def _ordered_candidates(self, providers: list[AIProvider]) -> list[tuple[AIProvider, str]]:
        """Flatten the pool so no paid model can run before an available free model."""
        candidates: list[tuple[AIProvider, str]] = []
        for provider in providers:
            for model in provider.models:
                candidates.append((provider, model))
        candidates.sort(key=lambda item: (not self._is_free_model(item[1]), item[0].priority, item[1]))
        return candidates

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        providers = self.providers()
        if not providers:
            raise AIProviderError("No AI provider is configured")
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        if timeout_seconds is None:
            timeout_seconds = self.settings.AI_AGENT_TIMEOUT_SECONDS
        try:
            timeout_seconds = max(5, min(int(timeout_seconds), 180))
        except (TypeError, ValueError):
            timeout_seconds = min(max(self.settings.AI_AGENT_TIMEOUT_SECONDS, 5), 180)

        last: AIProviderError | None = None
        now = time.time()
        candidates = self._ordered_candidates(providers)
        attempted_free = False
        for provider, model in candidates:
            model_key = f"{provider.name}:{model}"
            if self._cooldown_until.get(provider.name, 0) > now:
                continue
            if self._model_cooldown_until.get(model_key, 0) > now:
                continue
            if self._is_free_model(model):
                attempted_free = True
            elif attempted_free is False and any(self._is_free_model(m) for _, m in candidates):
                # Defensive guard: never enter paid while a free candidate is still eligible.
                continue

            payload = {"model": model, "messages": messages, **kwargs}
            request = urllib.request.Request(
                provider.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=self._headers(provider),
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                if not isinstance(data, dict):
                    raise AIProviderError(f"Invalid AI provider response: {provider.name}/{model}", provider=provider.name)
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
                if self._is_rate_limited(exc.code, body):
                    cooldown = min(retry_after or 300, 86400)
                    self._model_cooldown_until[model_key] = time.time() + cooldown
                    last = AIProviderError(f"model rate limited: {provider.name}/{model}", retryable=True, retry_after=cooldown, provider=provider.name)
                    continue
                if exc.code in {408, 409, 500, 502, 503, 504}:
                    self._model_cooldown_until[model_key] = time.time() + 30
                    last = AIProviderError(f"provider HTTP {exc.code}: {provider.name}/{model}", retryable=True, provider=provider.name)
                else:
                    last = AIProviderError(f"provider HTTP {exc.code}: {provider.name}/{model}", provider=provider.name)
                continue
            except (urllib.error.URLError, TimeoutError):
                self._model_cooldown_until[model_key] = time.time() + 30
                last = AIProviderError(f"provider unavailable: {provider.name}/{model}", retryable=True, provider=provider.name)
                continue
            except (json.JSONDecodeError, ValueError, TypeError):
                self._model_cooldown_until[model_key] = time.time() + 30
                last = AIProviderError(f"provider returned invalid response: {provider.name}/{model}", provider=provider.name)
                continue

        raise last or AIProviderError("All configured AI models are cooling down", retryable=True)

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
