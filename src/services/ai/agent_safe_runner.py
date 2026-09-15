"""Safe execution wrapper for RahYar AI agents.

Keeps failures in one agent from breaking the Telegram bot update flow.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class AgentSafeRunner:
    async def run(
        self,
        agent_name: str,
        action: Callable[[], Awaitable[Any]],
        fallback: Any = None,
        **context: Any,
    ) -> Any:
        try:
            return await action()
        except Exception as exc:
            logger.exception(
                "ai_agent_failed",
                extra={
                    "agent": agent_name,
                    "context": context,
                    "exception": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            return fallback


agent_safe_runner = AgentSafeRunner()
