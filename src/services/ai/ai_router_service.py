"""AI provider routing layer.

Central place for model selection, retries and fallback behaviour.
The concrete providers can be plugged in without changing bot or web code.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger("rahyar.ai.router")

AIHandler = Callable[[str], Awaitable[str]]


@dataclass
class AIProvider:
    name: str
    handler: AIHandler
    priority: int = 100
    cooldown_seconds: int = 60
    failures: int = 0
    unavailable_until: float = 0

    def available(self) -> bool:
        return time.time() >= self.unavailable_until

    def mark_failure(self) -> None:
        self.failures += 1
        delay = min(self.cooldown_seconds * (2 ** (self.failures - 1)), 1800)
        self.unavailable_until = time.time() + delay

    def mark_success(self) -> None:
        self.failures = 0
        self.unavailable_until = 0


class AIRouter:
    def __init__(self) -> None:
        self._providers: list[AIProvider] = []

    def register(self, provider: AIProvider) -> None:
        self._providers.append(provider)
        self._providers.sort(key=lambda item: item.priority)

    async def ask(self, prompt: str) -> dict[str, Any]:
        errors: list[str] = []

        candidates = [p for p in self._providers if p.available()]

        for provider in candidates:
            try:
                result = await asyncio.wait_for(
                    provider.handler(prompt),
                    timeout=30,
                )
                provider.mark_success()
                return {
                    "provider": provider.name,
                    "response": result,
                    "fallback_used": provider != self._providers[0],
                }
            except Exception as exc:
                provider.mark_failure()
                logger.warning("AI provider %s failed: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")

        return {
            "provider": None,
            "response": "AI service temporarily unavailable",
            "errors": errors,
        }


ai_router = AIRouter()
