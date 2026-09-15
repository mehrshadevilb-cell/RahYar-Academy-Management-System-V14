from __future__ import annotations

from typing import Any

from src.database.models.ai_provider import AIProvider
from src.integrations.ai.registry import ProviderRegistry
from src.services.ai.credential_crypto import decrypt_api_key


async def discover_models(provider: AIProvider) -> list[dict[str, Any]]:
    """Discover and normalize provider models without mutating the database."""
    if not provider.is_active:
        raise ValueError("Cannot discover models from an inactive provider")
    client = ProviderRegistry.get_client(provider, decrypt_api_key(provider.api_key_encrypted))
    models = await client.list_models()
    normalized: list[dict[str, Any]] = []
    for model in models:
        model_id = model.get("model_id") or model.get("id")
        if not model_id:
            continue
        normalized.append({
            "model_id": str(model_id),
            "display_name": str(model.get("display_name") or model_id),
            "context_window": model.get("context_window"),
            "max_output_tokens": model.get("max_output_tokens"),
            "supports_vision": bool(model.get("supports_vision", provider.supports_vision)),
            "supports_tools": bool(model.get("supports_tools", provider.supports_tools)),
            "supports_streaming": bool(model.get("supports_streaming", provider.supports_streaming)),
            "pricing_input": model.get("pricing_input"),
            "pricing_output": model.get("pricing_output"),
            "raw_metadata": model.get("raw_metadata", model),
        })
    return normalized
