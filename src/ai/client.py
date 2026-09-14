from __future__ import annotations

from typing import Any

import httpx

from src.core.config.settings import get_settings


class AIClient:
    """OpenAI-compatible client used by RahYar AI agents."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.AI_AGENT_API_KEY or getattr(settings, "AI_API_KEY", None)
        self.base_url = settings.AI_AGENT_BASE_URL or getattr(settings, "AI_BASE_URL", "")
        self.model = settings.AI_AGENT_MODEL or getattr(settings, "AI_MODEL", "")
        self.timeout = settings.AI_AGENT_TIMEOUT_SECONDS

    async def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("AI API key is not configured")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()


ai_client = AIClient()
