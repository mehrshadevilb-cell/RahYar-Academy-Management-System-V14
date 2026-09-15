from __future__ import annotations

import os

from src.database.models.ai_provider import AIProvider
from src.integrations.ai.provider_catalog import PROVIDER_PRESETS
from src.services.ai.credential_crypto import encrypt_api_key


class AIProviderBootstrapService:
    """Provision known gateways from environment variables without hard-coding secrets."""

    def __init__(self, session):
        self.session = session

    def provision_configured(self) -> list[AIProvider]:
        providers: list[AIProvider] = []
        for preset in PROVIDER_PRESETS:
            if not preset.api_key_env:
                continue
            api_key = os.getenv(preset.api_key_env, "").strip()
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
                # Keep DB configuration authoritative, but refresh the credential
                # when the environment explicitly supplies a new key.
                provider.base_url = preset.base_url
                provider.provider_type = preset.provider_type
                provider.api_key_encrypted = encrypt_api_key(api_key)
                provider.is_active = True
            providers.append(provider)

        if providers:
            self.session.commit()
            for provider in providers:
                self.session.refresh(provider)
        return providers
