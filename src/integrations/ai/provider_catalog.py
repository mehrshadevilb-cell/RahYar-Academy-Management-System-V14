from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderPreset:
    name: str
    display_name: str
    base_url: str
    provider_type: str = "openai_compatible"
    api_key_env: str | None = None
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_tools: bool = True
    extra_config: dict[str, Any] | None = None


# Known gateways. API keys stay in environment variables and are encrypted
# before being persisted to the database. Model IDs are intentionally not
# hard-coded: every provider is discovered through its live models endpoint.
PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        name="orcarouter",
        display_name="OrcaRouter",
        base_url="https://api.orcarouter.ai/v1",
        api_key_env="ORCAROUTER_API_KEY",
    ),
    ProviderPreset(
        name="kiraai",
        display_name="KiraAI",
        base_url="https://kiraai.vn/api/v1",
        api_key_env="KIRAAI_API_KEY",
    ),
    ProviderPreset(
        name="openrouter",
        display_name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        supports_vision=True,
    ),
    ProviderPreset(
        name="agentrouter",
        display_name="AgentRouter",
        base_url="https://co.agentrouter.org/v1",
        api_key_env="AGENTROUTER_API_KEY",
        supports_vision=True,
    ),
    ProviderPreset(
        name="google",
        display_name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        provider_type="google",
        api_key_env="GOOGLE_API_KEY",
        supports_vision=True,
    ),
    ProviderPreset(
        name="bytez",
        display_name="Bytez",
        base_url="https://api.bytez.com/models/v2/openai/v1",
        api_key_env="BYTEZ_API_KEY",
        extra_config={
            "auth_scheme": "raw",
            "models_key": "output",
            "model_id_key": "modelId",
        },
    ),
    ProviderPreset(
        name="dahl",
        display_name="Dahl",
        base_url="https://inference.dahl.global/v1",
        api_key_env="DAHL_API_KEY",
    ),
)


def get_provider_preset(name: str) -> ProviderPreset:
    normalized = name.strip().lower()
    for preset in PROVIDER_PRESETS:
        if preset.name == normalized:
            return preset
    raise KeyError(f"Unknown AI provider preset: {name}")
