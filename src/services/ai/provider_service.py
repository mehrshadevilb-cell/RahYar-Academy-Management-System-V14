from __future__ import annotations

from src.database.models.ai_provider import AIProvider
from src.services.ai.credential_crypto import encrypt_api_key


class AIProviderService:
    def __init__(self, session):
        self.session = session

    def create(
        self,
        *,
        name: str,
        display_name: str,
        base_url: str,
        api_key: str,
        provider_type: str = "openai_compatible",
        extra_config: dict | None = None,
        supports_streaming: bool = True,
        supports_vision: bool = False,
        supports_tools: bool = True,
    ) -> AIProvider:
        provider = AIProvider(
            name=name.strip().lower(),
            display_name=display_name.strip(),
            base_url=base_url.rstrip("/"),
            api_key_encrypted=encrypt_api_key(api_key),
            provider_type=provider_type.strip().lower(),
            extra_config=extra_config or {},
            supports_streaming=supports_streaming,
            supports_vision=supports_vision,
            supports_tools=supports_tools,
        )
        self.session.add(provider)
        self.session.commit()
        self.session.refresh(provider)
        return provider

    def get(self, provider_id):
        return self.session.get(AIProvider, provider_id)

    def list_active(self) -> list[AIProvider]:
        return self.session.query(AIProvider).filter(AIProvider.is_active.is_(True)).order_by(AIProvider.name).all()

    def set_active(self, provider_id, active: bool) -> AIProvider:
        provider = self.session.get(AIProvider, provider_id)
        if provider is None:
            raise ValueError("AI provider not found")
        provider.is_active = active
        self.session.commit()
        self.session.refresh(provider)
        return provider

    def rotate_api_key(self, provider_id, api_key: str) -> AIProvider:
        provider = self.session.get(AIProvider, provider_id)
        if provider is None:
            raise ValueError("AI provider not found")
        provider.api_key_encrypted = encrypt_api_key(api_key)
        self.session.commit()
        self.session.refresh(provider)
        return provider
