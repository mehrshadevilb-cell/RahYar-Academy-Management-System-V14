"""AI provider routing layer.

Central place for model selection, retries and fallback behaviour.
The concrete providers can be plugged in without changing bot or web code.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger("rahyar.ai.router")

AIHandler = Callable[[str], Awaitable[str]]


@dataclass
class AIProvider:
    name: str
    handler: AIHandler
    priority: int = 100


class AIRouter:
    def __init__(self) -> None:
        self._providers: list[AIProvider] = []

    def register(self, provider: AIProvider) -> None:
        self._providers.append(provider)
        self._providers.sort(key=lambda item: item.priority)

    async def ask(self, prompt: str) -> dict[str, Any]:
        errors: list[str] = []

        for provider in self._providers:
            try:
                result = await asyncio.wait_for(
                    provider.handler(prompt),
                    timeout=30,
                )
                return {
                    "provider": provider.name,
                    "response": result,
                    "fallback_used": provider != self._providers[0],
                }
            except Exception as exc:
                logger.warning("AI provider %s failed: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")

        return {
            "provider": None,
            "response": "AI service temporarily unavailable",
            "errors": errors,
        }


ai_router = AIRouter()
