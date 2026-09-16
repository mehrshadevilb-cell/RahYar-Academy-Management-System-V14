from __future__ import annotations

from src.ai.shared_router import get_shared_router


async def check_ai_health() -> dict[str, str | bool | int]:
    router = get_shared_router()
    try:
        providers = router.providers()
        candidates = router._ordered_candidates(providers)
        data = router.chat(
            [{"role": "user", "content": "Reply only with OK"}],
            temperature=0,
            max_tokens=8,
            timeout_seconds=15,
        )
        return {
            "status": True,
            "message": "AI provider reachable",
            "provider": str(data.get("_rahyar_provider") or ""),
            "model": str(data.get("_rahyar_model") or ""),
            "free": bool(data.get("_rahyar_is_free")),
            "candidate_count": len(candidates),
            "cooldown_count": len(router.cooldown_snapshot()),
        }
    except Exception as exc:
        return {"status": False, "message": str(exc)[:300]}
