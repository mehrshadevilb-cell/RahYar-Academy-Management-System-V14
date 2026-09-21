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
# Render deployment marker: provider bootstrap catalog is deployed from main.
PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset("orcarouter", "OrcaRouter", "https://api.orcarouter.ai/v1", api_key_env="ORCAROUTER_API_KEY"),
    ProviderPreset("kiraai", "KiraAI", "https://kiraai.vn/api/v1", api_key_env="KIRAAI_API_KEY"),
    ProviderPreset("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", api_key_env="OPENROUTER_API_KEY", supports_vision=True),
    ProviderPreset("agentrouter", "AgentRouter", "https://agentrouter.org/v1", api_key_env="AGENTROUTER_API_KEY", supports_vision=True),
    ProviderPreset("openai", "OpenAI", "https://api.openai.com/v1", api_key_env="OPENAI_API_KEY", supports_vision=True),
    ProviderPreset("google", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta", provider_type="google", api_key_env="GOOGLE_API_KEY", supports_vision=True),
    ProviderPreset("gemini", "Gemini", "https://generativelanguage.googleapis.com/v1beta", provider_type="google", api_key_env="GEMINI_API_KEY", supports_vision=True),
    ProviderPreset("anthropic", "Anthropic", "https://api.anthropic.com/v1", provider_type="anthropic", api_key_env="ANTHROPIC_API_KEY", supports_vision=True),
    ProviderPreset("xkiro", "XKiro", "https://api.xkiro.com/v1", api_key_env="XKIRO_API_KEY"),
    ProviderPreset("groq", "Groq", "https://api.groq.com/openai/v1", api_key_env="GROQ_API_KEY"),
    ProviderPreset("deepseek", "DeepSeek", "https://api.deepseek.com/v1", api_key_env="DEEPSEEK_API_KEY"),
    ProviderPreset("mistral", "Mistral", "https://api.mistral.ai/v1", api_key_env="MISTRAL_API_KEY"),
    ProviderPreset("together", "Together AI", "https://api.together.xyz/v1", api_key_env="TOGETHER_API_KEY"),
    ProviderPreset("fireworks", "Fireworks AI", "https://api.fireworks.ai/inference/v1", api_key_env="FIREWORKS_API_KEY"),
    ProviderPreset("cerebras", "Cerebras", "https://api.cerebras.ai/v1", api_key_env="CEREBRAS_API_KEY"),
    ProviderPreset("sambanova", "SambaNova", "https://api.sambanova.ai/v1", api_key_env="SAMBANOVA_API_KEY"),
    ProviderPreset("deepinfra", "DeepInfra", "https://api.deepinfra.com/v1/openai", api_key_env="DEEPINFRA_API_KEY"),
    ProviderPreset("nebius", "Nebius", "https://api.tokenfactory.nebius.com/v1", api_key_env="NEBIUS_API_KEY"),
    ProviderPreset("nvidia", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1", api_key_env="NVIDIA_API_KEY"),
    ProviderPreset("perplexity", "Perplexity", "https://api.perplexity.ai", api_key_env="PERPLEXITY_API_KEY"),
    ProviderPreset("cohere", "Cohere", "https://api.cohere.com/compatibility/v1", api_key_env="COHERE_API_KEY"),
    ProviderPreset("huggingface", "Hugging Face", "https://router.huggingface.co/v1", api_key_env="HUGGINGFACE_API_KEY"),
    ProviderPreset("novita", "Novita AI", "https://api.novita.ai/openai", api_key_env="NOVITA_API_KEY"),
    ProviderPreset("siliconflow", "SiliconFlow", "https://api.siliconflow.com/v1", api_key_env="SILICONFLOW_API_KEY"),
    ProviderPreset("chutes", "Chutes", "https://llm.chutes.ai/v1", api_key_env="CHUTES_API_KEY"),
    ProviderPreset("xai", "xAI", "https://api.x.ai/v1", api_key_env="XAI_API_KEY"),
    ProviderPreset(
        name="bytez",
        display_name="Bytez",
        base_url="https://api.bytez.com/models/v2/openai/v1",
        api_key_env="BYTEZ_API_KEY",
        extra_config={
            "auth_scheme": "raw",
            "models_url": "https://api.bytez.com/models/v2/list/models?task=chat",
            "models_key": "output",
            "model_id_key": "modelId",
            "discovery_health_url": "https://api.bytez.com/models/v2/list/tasks",
        },
    ),
    ProviderPreset("dahl", "Dahl", "https://inference.dahl.global/v1", api_key_env="DAHL_API_KEY"),
)
)


def get_provider_preset(name: str) -> ProviderPreset:
    normalized = name.strip().lower()
    for preset in PROVIDER_PRESETS:
        if preset.name == normalized:
            return preset
    raise KeyError(f"Unknown AI provider preset: {name}")
