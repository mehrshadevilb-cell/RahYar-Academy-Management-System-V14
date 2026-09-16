"""Opt-in, rate-limited automatic fix attempts for production errors.

Safety contract (non-negotiable):
- Disabled unless AI_AGENT_AUTO_FIX_ON_ERROR=true
- Writes only on ai/* branches via the existing agent pipeline
- Never merges to main / never deploys
- Deduplicates identical error fingerprints
- Notifies the owner with the result
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass

from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.services.ai_agent_runtime import runtime
from src.services.ai_agent_service import AIAgentError

logger = get_logger("rahyar.ai_auto_fix")


@dataclass
class AutoFixDecision:
    accepted: bool
    reason: str
    fingerprint: str = ""


class AIAgentAutoFixService:
    """Queues bounded auto-fix tasks from runtime exceptions."""

    COOLDOWN_SECONDS = 15 * 60
    MAX_TRACE_CHARS = 2500
    MAX_MESSAGE_CHARS = 400

    def __init__(self) -> None:
        self.settings = get_settings()
        self._recent: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._in_flight: set[str] = set()

    def _fingerprint(self, exc: BaseException) -> str:
        text = f"{type(exc).__name__}:{exc}"
        # Collapse volatile digits (ids, timestamps) so retries group together.
        normalized = re.sub(r"\d+", "#", text)[:800]
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def evaluate(self, exc: BaseException) -> AutoFixDecision:
        if not self.settings.AI_AGENT_AUTO_FIX_ON_ERROR:
            return AutoFixDecision(False, "auto-fix disabled (set AI_AGENT_AUTO_FIX_ON_ERROR=true)")
        if not self.settings.AI_AGENT_ENABLED:
            return AutoFixDecision(False, "AI agent disabled")
        if not self.settings.github_write_ready and not True:
            # github_write_ready is preferred online; local git also works via agent.
            pass
        # Skip noisy / non-actionable classes early.
        name = type(exc).__name__
        if name in {"TelegramConflictError", "TelegramUnauthorizedError", "CancelledError"}:
            return AutoFixDecision(False, f"skipped exception type {name}")
        fp = self._fingerprint(exc)
        last = self._recent.get(fp, 0.0)
        if time.time() - last < self.COOLDOWN_SECONDS:
            return AutoFixDecision(False, "duplicate fingerprint within cooldown", fp)
        if fp in self._in_flight:
            return AutoFixDecision(False, "auto-fix already in flight for fingerprint", fp)
        return AutoFixDecision(True, "accepted", fp)

    def _task_prompt(self, exc: BaseException, traceback_text: str) -> str:
        tb = (traceback_text or "")[-self.MAX_TRACE_CHARS :]
        msg = str(exc)[: self.MAX_MESSAGE_CHARS]
        return (
            "AUTOMATIC BUG FIX TASK (owner-approved opt-in)\n"
            "A production exception was captured. Propose the smallest safe fix on ai/*.\n"
            "Never merge to main. Never touch secrets, payment approval, or admin auth.\n"
            "Follow debug.md skill: evidence → root cause → minimal patch → regression test.\n\n"
            f"Exception type: {type(exc).__name__}\n"
            f"Message: {msg}\n\n"
            f"Traceback (tail):\n{tb}\n"
        )

    async def maybe_schedule(
        self,
        *,
        owner_telegram_id: int,
        exc: BaseException,
        traceback_text: str,
        notify,
    ) -> AutoFixDecision:
        """Schedule an auto-fix when policy allows. `notify` is an async callable(str)."""
        decision = self.evaluate(exc)
        if not decision.accepted:
            return decision

        async with self._lock:
            # Re-check under lock.
            decision = self.evaluate(exc)
            if not decision.accepted:
                return decision
            self._recent[decision.fingerprint] = time.time()
            self._in_flight.add(decision.fingerprint)

        async def _run() -> None:
            fp = decision.fingerprint
            try:
                await notify(
                    "🛠 <b>Auto-Fix شروع شد</b>\n"
                    f"Fingerprint: <code>{fp}</code>\n"
                    f"Error: <code>{type(exc).__name__}: {str(exc)[:180]}</code>\n"
                    "Agent فقط روی branch <code>ai/*</code> کار می‌کند و merge خودکار ندارد."
                )

                async def progress(text: str) -> None:
                    # Keep owner updates sparse.
                    if any(token in text for token in ("Planner", "pytest", "PR", "خطا", "failed")):
                        await notify(text[:500])

                result = await runtime.run_write(
                    owner_telegram_id,
                    self._task_prompt(exc, traceback_text),
                    "fix",
                    progress,
                )
                await notify(
                    "✅ <b>Auto-Fix تمام شد</b>\n"
                    f"Fingerprint: <code>{fp}</code>\n\n"
                    f"{result[:3500]}"
                )
            except AIAgentError as agent_exc:
                logger.warning("auto-fix failed: %s", agent_exc)
                await notify(
                    f"❌ Auto-Fix ناموفق\n<code>{fp}</code>\n{str(agent_exc)[:800]}"
                )
            except Exception as unexpected:
                logger.exception("auto-fix crashed")
                await notify(
                    f"❌ Auto-Fix با خطای داخلی متوقف شد\n<code>{fp}</code>\n"
                    f"{type(unexpected).__name__}: {str(unexpected)[:400]}"
                )
            finally:
                self._in_flight.discard(fp)

        asyncio.create_task(_run())
        return decision


auto_fix_service = AIAgentAutoFixService()
