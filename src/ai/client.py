from __future__ import annotations

from typing import Any

import httpx

from src.core.config.settings import get_settings


class AIDeveloperClient:
    """Small OpenAI-compatible client for RahYar AI Developer Agent."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.AI_AGENT_API_KEY
        self.base_url = settings.AI_AGENT_BASE_URL.rstrip("/")
        self.model = settings.AI_AGENT_MODEL
        self.timeout = settings.AI_AGENT_TIMEOUT_SECONDS

    async def chat(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("AI_AGENT_API_KEY is not configured")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            return response.json()
