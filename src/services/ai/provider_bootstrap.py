from __future__ import annotations

from src.core.config.settings import get_settings
from src.database.models.ai_provider import AIProvider
from src.integrations.ai.provider_catalog import PROVIDER_PRESETS
from src.services.ai.credential_crypto import encrypt_api_key


class AIProviderBootstrapService:
    """Provision configured gateways from runtime settings without exposing secrets."""

    def __init__(self, session):
        self.session = session
        self.settings = get_settings()

    def _api_key(self, env_name: str | None) -> str:
        if not env_name:
            return ""
        # Pydantic Settings reads both process env and .env. Resolve the
        # requested provider key through the Settings object first so local,
        # Docker and Render deployments behave consistently.
        value = getattr(self.settings, env_name, None)
        if value is None:
            import os

            value = os.getenv(env_name, "")
        return str(value or "").strip()

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
            else:
                # Environment is an explicit deployment configuration. Refresh
                # the encrypted credential and endpoint, but preserve DB-only
                # metadata such as model records and admin activation state.
                provider.base_url = preset.base_url
                provider.provider_type = preset.provider_type
                provider.api_key_encrypted = encrypt_api_key(api_key)
                provider.is_active = True
                provider.supports_streaming = preset.supports_streaming
                provider.supports_vision = preset.supports_vision
                provider.supports_tools = preset.supports_tools
            providers.append(provider)

        if providers:
            self.session.commit()
            for provider in providers:
                self.session.refresh(provider)
        return providers
