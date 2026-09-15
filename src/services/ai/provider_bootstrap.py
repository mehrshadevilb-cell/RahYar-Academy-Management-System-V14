from __future__ import annotations

from sqlalchemy import or_

from src.core.config.settings import get_settings
from src.database.models.ai_model import AIModel
from src.database.models.ai_provider import AIProvider
from src.integrations.ai.provider_catalog import PROVIDER_PRESETS
from src.services.ai.credential_crypto import encrypt_api_key


STALE_AGENTROUTER_MODELS = {"mimo-v2.5-free", "mimo-v2.5"}


class AIProviderBootstrapService:
    """Provision configured gateways from runtime settings without exposing secrets."""

    def __init__(self, session):
        self.session = session
        self.settings = get_settings()

    def _api_key(self, env_name: str | None) -> str:
        if not env_name:
            return ""
        value = getattr(self.settings, env_name, None)
        if value is None:
            import os

            value = os.getenv(env_name, "")
        return str(value or "").strip()

    def _repair_stale_models(self, provider: AIProvider) -> None:
        """Remove known-dead AgentRouter model IDs from persisted runtime state.

        Older deployments persisted mimo-v2.5(-free), which now returns HTTP 404.
        Keeping it active makes every Agent request hit the dead model before any
        healthy provider can be considered. Prefer the configured fallback model
        when one is explicitly available, otherwise deactivate the stale row.
        """
        if provider.name.strip().lower() != "agentrouter":
            return

        fallback = (self.settings.AI_FALLBACK_MODEL or "").strip()
        stale_rows = (
            self.session.query(AIModel)
            .filter(AIModel.provider_id == provider.id)
            .filter(AIModel.is_active.is_(True))
            .filter(AIModel.model_id.in_(STALE_AGENTROUTER_MODELS))
            .all()
        )
        if not stale_rows:
            return

        for model in stale_rows:
            if fallback and fallback.lower() not in STALE_AGENTROUTER_MODELS:
                model.model_id = fallback
                model.display_name = fallback
                model.is_active = True
                model.is_default = True
            else:
                model.is_active = False
                model.is_default = False

        # Never leave multiple defaults after replacing a stale model.
        if fallback and fallback.lower() not in STALE_AGENTROUTER_MODELS:
            others = (
                self.session.query(AIModel)
                .filter(AIModel.provider_id == provider.id)
                .filter(AIModel.is_active.is_(True))
                .filter(AIModel.model_id != fallback)
                .all()
            )
            for model in others:
                model.is_default = False

    def provision_configured(self) -> list[AIProvider]:
        providers: list[AIProvider] = []
        for preset in PROVIDER_PRESETS:
            api_key = self._api_key(preset.api_key_env)
            if not api_key:
                continue

            provider = (
                self.session.query(AIProvider)
                .filter(AIProvider.name == preset.name)
                .one_or_none()
            )
            if provider is None:
                provider = AIProvider(
                    name=preset.name,
                    display_name=preset.display_name,
                    base_url=preset.base_url,
                    api_key_encrypted=encrypt_api_key(api_key),
                    provider_type=preset.provider_type,
                    is_active=True,
                    supports_streaming=preset.supports_streaming,
                    supports_vision=preset.supports_vision,
                    supports_tools=preset.supports_tools,
                )
                self.session.add(provider)
                self.session.flush()
            else:
                provider.base_url = preset.base_url
                provider.provider_type = preset.provider_type
                provider.api_key_encrypted = encrypt_api_key(api_key)
                provider.is_active = True
                provider.supports_streaming = preset.supports_streaming
                provider.supports_vision = preset.supports_vision
                provider.supports_tools = preset.supports_tools

            self._repair_stale_models(provider)
            providers.append(provider)

        if providers:
            self.session.commit()
            for provider in providers:
                self.session.refresh(provider)
        return providers
