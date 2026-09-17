"""Bridge RahYar AI services to the ArtistYar website.

The public website uses the same read-only ChatAssistantService as the
Telegram assistant. Provider discovery, failover, knowledge context and
pricing/catalog context therefore stay centralized in the bot instead of
being duplicated in the Next.js application.
"""
from __future__ import annotations

import asyncio
import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.services.ai_agent_runtime import runtime
from src.services.chat_assistant_service import ChatAssistantError, ChatAssistantService
from src.web.deps import get_db

logger = get_logger("web.api_ai")
settings = get_settings()
router = APIRouter(prefix="/api/v1", tags=["ai-bridge"])
assistant = ChatAssistantService()


def _require_api_key(x_rahyar_key: str | None = Header(default=None)) -> None:
    """Protect diagnostics when WEB_API_SECRET is configured."""
    secret = (os.getenv("WEB_API_SECRET") or "").strip()
    if not secret:
        return
    if not x_rahyar_key or x_rahyar_key != secret:
        raise HTTPException(status_code=401, detail="invalid_api_key")


def _require_ai_bridge_key(x_rahyar_ai_key: str | None = Header(default=None)) -> None:
    """Require a dedicated server-to-server secret for ArtistYar AI traffic."""
    secret = (os.getenv("RAHYAR_AI_BRIDGE_SECRET") or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="ai_bridge_not_configured")
    if not x_rahyar_ai_key or x_rahyar_ai_key != secret:
        raise HTTPException(status_code=401, detail="invalid_ai_bridge_key")


class AssistantIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    client_id: str | None = Field(default=None, max_length=64)


@router.get("/ai/status")
async def ai_status(_: None = Depends(_require_api_key)):
    """Diagnostics shared with the website admin panel."""
    self_check = await asyncio.to_thread(runtime.self_check)
    plain = re.sub(r"<[^>]+>", "", self_check).replace("&nbsp;", " ")
    agent_status = "unavailable"
    try:
        agent_status = await asyncio.to_thread(runtime.agent.status)
        lines = []
        for line in agent_status.splitlines():
            if line.startswith("base_url="):
                lines.append("provider=Configured (endpoint hidden)")
            elif line.startswith("repo="):
                lines.append("repository=Configured")
            else:
                lines.append(line)
        agent_status = "\n".join(lines)
    except Exception as exc:
        agent_status = f"error: {type(exc).__name__}"
        logger.exception("ai status failed")

    return {
        "ok": True,
        "chat_assistant_enabled": bool(settings.CHAT_ASSISTANT_ENABLED),
        "self_check": plain[:4000],
        "agent_status": str(agent_status)[:2000],
        "note": "Write tasks (Fix/Feature) remain Telegram-only for security.",
    }


@router.post("/assistant/chat")
async def assistant_chat(
    body: AssistantIn,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_require_ai_bridge_key),
):
    """ArtistYar website chat using the exact Telegram read-only assistant stack."""
    if not settings.CHAT_ASSISTANT_ENABLED:
        raise HTTPException(status_code=503, detail="assistant_disabled")

    client = (body.client_id or "").strip() or (
        request.client.host if request.client else "web-anonymous"
    )
    rate_key = f"web:{client[:64]}"

    try:
        reply = await asyncio.to_thread(assistant.answer, db, rate_key, body.message)
    except ChatAssistantError as exc:
        code = str(exc)
        if code == "disabled":
            raise HTTPException(status_code=503, detail="assistant_disabled") from exc
        if code == "not_configured":
            raise HTTPException(status_code=503, detail="assistant_not_configured") from exc
        if code == "empty_message":
            raise HTTPException(status_code=400, detail="empty_message") from exc
        if code in {"provider_unavailable", "provider_rate_limited"}:
            raise HTTPException(status_code=502, detail=code) from exc
        raise HTTPException(status_code=429, detail=code) from exc
    except Exception:
        logger.exception("assistant_chat failed")
        raise HTTPException(status_code=500, detail="assistant_failed") from None

    return {
        "ok": True,
        "reply": reply,
        "source": "rahyar-chat-assistant",
        "sync": "centralized-provider-router",
    }
