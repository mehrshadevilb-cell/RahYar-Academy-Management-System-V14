from __future__ import annotations

from typing import Any

from src.ai.provider_router import AIProviderError, AIProviderRouter


class AIClient:
    """Small OpenAI-compatible client backed by the multi-provider router."""

    MAX_PROMPT_CHARS = 16_000

    def __init__(self) -> None:
        self.router = AIProviderRouter()

    async def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("AI prompt cannot be empty")
        if len(prompt) > self.MAX_PROMPT_CHARS:
            raise ValueError("AI prompt is too large")
        try:
            return self.router.chat(
                [{"role": "user", "content": prompt}],
                **kwargs,
            )
        except AIProviderError as exc:
            raise RuntimeError(str(exc)) from exc


ai_client = AIClient()
