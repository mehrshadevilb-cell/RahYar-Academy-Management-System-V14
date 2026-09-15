from __future__ import annotations

from typing import Any

from src.ai.provider_router import AIProviderError, AIProviderRouter
from src.services.ai_agent_service import AIAgentError, AIAgentService


class RoutedAIAgentService(AIAgentService):
    """AI Agent service using the DB-backed free-first provider router."""

    def __init__(self) -> None:
        super().__init__()
        self.router = AIProviderRouter()

    def _api_key(self) -> str:
        # The router may be configured entirely from encrypted DB credentials;
        # the legacy base service should not reject that configuration.
        if self.router.providers():
            return "router-managed"
        return super()._api_key()

    def _base_url(self) -> str:
        providers = self.router.providers()
        if providers:
            return providers[0].base_url
        return super()._base_url()

    def _model(self) -> str:
        providers = self.router.providers()
        if providers:
            return providers[0].model
        return super()._model()

    def _request_model(self, prompt: str) -> str:
        try:
            data = self.router.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are the RahYar senior software engineer. "
                            "Follow project architecture. Never include secrets. "
                            "Return concise engineering output."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                timeout_seconds=self.settings.AI_AGENT_TIMEOUT_SECONDS,
            )
            return str(data["choices"][0]["message"]["content"])
        except AIProviderError as exc:
            detail = str(exc)
            if exc.retry_after:
                detail += f" (retry_after={exc.retry_after}s)"
            raise AIAgentError(f"AI provider router failed: {detail}") from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise AIAgentError("AI provider returned an unexpected response.") from exc

    def status(self) -> str:
        return super().status() + "\nrouter_status=" + repr(self.router.status())
