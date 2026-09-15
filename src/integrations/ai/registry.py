from __future__ import annotations

from typing import Type

from src.database.models.ai_provider import AIProvider
from src.integrations.ai.base import BaseAIProvider
from src.integrations.ai.providers.anthropic import AnthropicProvider
from src.integrations.ai.providers.google import GoogleProvider
from src.integrations.ai.providers.openai_compatible import OpenAICompatibleProvider


class ProviderRegistry:
    _providers: dict[str, Type[BaseAIProvider]] = {
        "openai_compatible": OpenAICompatibleProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
    }

    @classmethod
    def register(cls, provider_type: str, implementation: Type[BaseAIProvider]) -> None:
        cls._providers[provider_type] = implementation

    @classmethod
    def get_client(cls, provider: AIProvider, api_key: str) -> BaseAIProvider:
        try:
            implementation = cls._providers[provider.provider_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported AI provider type: {provider.provider_type}") from exc
        return implementation(provider.base_url, api_key, provider.extra_config or {})

    @classmethod
    def supported_types(cls) -> tuple[str, ...]:
        return tuple(sorted(cls._providers))
