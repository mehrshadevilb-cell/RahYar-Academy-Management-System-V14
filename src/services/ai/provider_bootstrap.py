from __future__ import annotations

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
        """Remove known-dead AgentRouter model IDs from persisted runtime state."""
        if provider.name.strip().lower() != "agentrouter":
            return

        fallback = (self.settings.AI_FALLBACK_MODEL or "").strip()
        fallback_valid = bool(fallback) and fallback.lower() not in STALE_AGENTROUTER_MODELS
        existing_fallback = None
        if fallback_valid:
            existing_fallback = (
                self.session.query(AIModel)
                .filter(AIModel.provider_id == provider.id)
                .filter(AIModel.model_id == fallback)
                .first()
            )

        stale_rows = (
            self.session.query(AIModel)
            .filter(AIModel.provider_id == provider.id)
            .filter(AIModel.is_active.is_(True))
            .filter(AIModel.model_id.in_(STALE_AGENTROUTER_MODELS))
            .all()
        )
        if not stale_rows:
            return

        if existing_fallback is not None:
            existing_fallback.is_active = True
            existing_fallback.is_default = True
            for model in stale_rows:
                model.is_active = False
                model.is_default = False
        elif fallback_valid:
            replacement = stale_rows[0]
            replacement.model_id = fallback
            replacement.display_name = fallback
            replacement.is_active = True
            replacement.is_default = True
            for model in stale_rows[1:]:
                model.is_active = False
                model.is_default = False
        else:
            for model in stale_rows:
                model.is_active = False
                model.is_default = False

        if fallback_valid:
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
                    extra_config=dict(preset.extra_config or {}),
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
                provider.extra_config = dict(preset.extra_config or {})

            self._repair_stale_models(provider)
            providers.append(provider)

        if providers:
            self.session.commit()
            for provider in providers:
                self.session.refresh(provider)
        return providers
