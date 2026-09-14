from __future__ import annotations

from typing import Any

import urllib.error
import urllib.request
import json

from src.core.config.settings import get_settings


class AIClient:
    """OpenAI-compatible client used by RahYar AI agents.

    Uses stdlib urllib (no extra httpx dependency) so health checks work
    with the same stack as AIAgentService.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.effective_ai_api_key
        self.base_url = settings.effective_ai_base_url
        self.model = settings.effective_ai_model
        self.timeout = settings.AI_AGENT_TIMEOUT_SECONDS

    async def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("AI API key is not configured")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }

        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"AI provider request failed: {exc}") from exc


ai_client = AIClient()
