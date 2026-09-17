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
    def __init__(self, message: str, *, retryable: bool = False, retry_after: int = 0, provider: str = "", rate_limited: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = max(0, retry_after)
        self.provider = provider
        self.rate_limited = rate_limited


class AIProviderRouter:
    """AI provider pool with DB discovery, global free-first routing and model failover."""

    _STALE_MODEL_IDS = {"mimo-v2.5-free", "mimo-v2.5"}
    _ENV_DISCOVERY_TTL_SECONDS = 300

    def __init__(self) -> None:
        self.settings = get_settings()
        self._cooldown_until: dict[str, float] = {}
        self._model_cooldown_until: dict[str, float] = {}
        self._env_model_cache: dict[tuple[str, str], tuple[float, tuple[str, ...]]] = {}

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

    @classmethod
    def _provider_from_env(cls, name: str, key_var: str, url_var: str, model_var: str, priority: int) -> AIProvider | None:
        key = (os.getenv(key_var) or "").strip()
        base_url = cls._normalize_base_url(os.getenv(url_var) or "")
        model = (os.getenv(model_var) or "").strip()
        if not (key and base_url and model):
            return None
        return AIProvider(name=name, api_key=key, base_url=base_url, models=(model,), priority=priority, provider_type=cls._infer_provider_type(name, base_url))

    @classmethod
    def _discoverable_provider_from_env(cls, name: str, key_var: str, url_var: str, model_var: str, priority: int) -> AIProvider | None:
        key = (os.getenv(key_var) or "").strip()
        base_url = cls._normalize_base_url(os.getenv(url_var) or "")
        model = (os.getenv(model_var) or "").strip()
        if not (key and base_url):
            return None
        models = (model,) if model else ()
        return AIProvider(name=name, api_key=key, base_url=base_url, models=models, priority=priority, provider_type=cls._infer_provider_type(name, base_url))

    @staticmethod
    def _is_free_model(model: Any) -> bool:
        if isinstance(model, str):
            model_id = model.lower()
            if model_id.startswith("@cf/"):
                return True
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
            return getattr(model, "pricing_input", None) is not None and getattr(model, "pricing_output", None) is not None and float(model.pricing_input) == 0.0 and float(model.pricing_output) == 0.0
        except (TypeError, ValueError):
            return False

    @classmethod
    def _is_stale_model_id(cls, model: str) -> bool:
        return (model or "").strip().lower() in cls._STALE_MODEL_IDS

    def _from_database(self) -> list[AIProvider]:
        try:
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
                    active_models.sort(key=lambda m: (not self._is_free_model(m), not m.is_default, -(m.context_window or 0), m.model_id))
                    try:
                        api_key = decrypt_api_key(provider.api_key_encrypted)
                    except Exception:
                        continue
                    models = tuple(m.model_id for m in active_models if not self._is_stale_model_id(m.model_id))
                    if not models:
                        continue
                    result.append(AIProvider(name=provider.name, api_key=api_key, base_url=self._normalize_base_url(provider.base_url), models=models, priority=index, provider_type=provider.provider_type or self._infer_provider_type(provider.name, provider.base_url)))
                return result
            finally:
                db.close()
        except Exception:
            return []

    def _env_providers(self) -> list[AIProvider]:
        providers: list[AIProvider] = []
        primary = self._provider_from_env("primary", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL", 10)
        if primary:
            providers.append(primary)
        secondary = self._provider_from_env("secondary", "AI2_API_KEY", "AI2_BASE_URL", "AI2_MODEL", 20)
        if secondary:
            providers.append(secondary)
        anthropic = self._discoverable_provider_from_env("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL", 30)
        xkiro = self._discoverable_provider_from_env("xkiro", "XKIRO_API_KEY", "XKIRO_BASE_URL", "XKIRO_MODEL", 40)
        if anthropic:
            providers.append(anthropic)
        if xkiro:
            providers.append(xkiro)

        # Cloudflare Workers AI (OpenAI-compatible /ai/v1)
        cf_token = (os.getenv("CLOUDFLARE_API_TOKEN") or getattr(self.settings, "CLOUDFLARE_API_TOKEN", None) or "").strip()
        cf_base = (getattr(self.settings, "cloudflare_ai_base_url", "") or os.getenv("CLOUDFLARE_AI_BASE_URL") or "").strip()
        if not cf_base:
            account_id = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or getattr(self.settings, "CLOUDFLARE_ACCOUNT_ID", None) or "").strip()
            if account_id:
                cf_base = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
        cf_model = (os.getenv("CLOUDFLARE_AI_MODEL") or getattr(self.settings, "CLOUDFLARE_AI_MODEL", None) or "@cf/meta/llama-3.1-8b-instruct").strip()
        if cf_token and cf_base and cf_model and not self._is_stale_model_id(cf_model):
            providers.append(
                AIProvider(
                    name="cloudflare",
                    api_key=cf_token,
                    base_url=self._normalize_base_url(cf_base),
                    models=(cf_model,),
                    priority=25,
                    provider_type="openai_compatible",
                )
            )

        if not providers and self.settings.effective_ai_api_key:
            base_url = self._normalize_base_url(self.settings.effective_ai_base_url)
            model = self.settings.effective_ai_model
            if not self._is_stale_model_id(model):
                providers.append(AIProvider(name="primary", api_key=self.settings.effective_ai_api_key, base_url=base_url, models=(model,), priority=100, provider_type=self._infer_provider_type("primary", base_url)))
        return providers
