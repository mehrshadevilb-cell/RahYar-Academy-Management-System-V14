"""Provider-pool adapter for AIAgentService."""
from __future__ import annotations

from src.ai.provider_router import AIProviderError, AIProviderRouter
from src.services.ai_agent_service import AIAgentError, AIAgentService


def _request_model(self: AIAgentService, prompt: str) -> str:
    try:
        data = self._provider_router.chat(
            [
                {"role": "system", "content": "You are the RahYar senior software engineer. Follow project architecture. Never include secrets. Return concise engineering output."},
                {"role": "user", "content": prompt[:16000]},
            ],
            temperature=0.1,
        )
        return str(data["choices"][0]["message"]["content"])
    except AIProviderError as exc:
        raise AIAgentError(
            f"AI provider pool unavailable; provider={exc.provider or 'pool'}; retry_after={exc.retry_after}"
        ) from exc


_original_init = AIAgentService.__init__


def _init(self: AIAgentService) -> None:
    _original_init(self)
    self._provider_router = AIProviderRouter()


AIAgentService.__init__ = _init
AIAgentService._request_model = _request_model

__all__ = ["AIAgentError", "AIAgentService"]
