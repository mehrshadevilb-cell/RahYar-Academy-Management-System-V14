from __future__ import annotations

from src.ai.client import ai_client


async def check_ai_health() -> dict[str, str | bool]:
    try:
        await ai_client.chat("Reply only with OK")
        return {"status": True, "message": "AI provider reachable"}
    except Exception as exc:
        return {"status": False, "message": str(exc)}
