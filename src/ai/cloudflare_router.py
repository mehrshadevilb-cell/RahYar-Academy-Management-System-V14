from __future__ import annotations

import time
from urllib.parse import urlparse

from src.ai.cloudflare_env import (
    discover_cloudflare_models,
    resolve_cloudflare_base_url,
    resolve_cloudflare_key,
    resolve_cloudflare_model,
)
from src.ai.provider_router import AIProvider, AIProviderRouter


class CloudflareAwareRouter(AIProviderRouter):
    """Extends the standard router with Cloudflare Workers AI env + model discovery."""

    def _env_providers(self):
        providers = list(super()._env_providers())
        cf_key = resolve_cloudflare_key()
        cf_base = resolve_cloudflare_base_url(self._normalize_base_url)
        cf_model = resolve_cloudflare_model()
        if cf_key and cf_base:
            models = (cf_model,) if cf_model and not self._is_stale_model_id(cf_model) else ()
            providers.append(
                AIProvider(
                    name="cloudflare",
                    api_key=cf_key,
                    base_url=cf_base,
                    models=models,
                    priority=25,
                    provider_type="openai_compatible",
                )
            )
        return providers

    def _discover_env_provider_models(self, provider: AIProvider, timeout_seconds: int = 10) -> AIProvider:
        host = (urlparse(provider.base_url).hostname or "").lower()
        if provider.models:
            return provider
        if provider.name.lower() == "cloudflare" or "cloudflare.com" in host:
            cache_key = (provider.name.lower(), provider.base_url.rstrip("/"))
            now = time.time()
            cached = self._env_model_cache.get(cache_key)
            if cached and cached[0] > now:
                return AIProvider(**{**provider.__dict__, "models": cached[1]})
            models = discover_cloudflare_models(provider.api_key, provider.base_url, timeout=timeout_seconds)
            unique = tuple(models)
            self._env_model_cache[cache_key] = (now + self._ENV_DISCOVERY_TTL_SECONDS, unique)
            return AIProvider(
                name=provider.name,
                api_key=provider.api_key,
                base_url=provider.base_url,
                models=unique,
                priority=provider.priority,
                enabled=provider.enabled,
                provider_type=provider.provider_type,
            )
        return super()._discover_env_provider_models(provider, timeout_seconds=timeout_seconds)


def get_ai_router() -> AIProviderRouter:
    return CloudflareAwareRouter()
