from __future__ import annotations

import time
from typing import Any

from src.ai.latency_aware_provider_router import LatencyAwareAIProviderRouter
from src.ai.provider_router import AIProviderError
from src.services.ai_agent_service import AIAgentError, AIAgentService
from src.services.provider_model_health_service import ProviderModelHealthService


class RoutedAIAgentService(AIAgentService):
    """AI Agent service using one live DB/env provider pool for every agent operation."""

    def __init__(self) -> None:
        super().__init__()
        self.router = LatencyAwareAIProviderRouter()
        self.model_health = ProviderModelHealthService(self.router)
        self._last_recovery_at: float = 0.0
        self._last_recovered_route: str | None = None

    def _api_key(self) -> str:
        if self.router.providers():
            return "router-managed"
        return super()._api_key()

    def _selected_candidate(self):
        providers = self.router.providers()
        candidates = self.router._ordered_candidates(providers)
        if not candidates:
            return None
        now = time.time()
        for provider, model in candidates:
            key = f"{provider.name}:{model}"
            if max(
                self.router._cooldown_until.get(provider.name, 0),
                self.router._model_cooldown_until.get(key, 0),
            ) <= now:
                return provider, model
        return candidates[0]

    def _base_url(self) -> str:
        selected = self._selected_candidate()
        return selected[0].base_url if selected else super()._base_url()

    def _model(self) -> str:
        selected = self._selected_candidate()
        return selected[1] if selected else super()._model()

    def recover_working_route(self, *, force: bool = False, prefer_fastest: bool = True) -> dict[str, Any]:
        now = time.time()
        if not force and self._last_recovery_at and now - self._last_recovery_at < 20:
            selected = self._selected_candidate()
            return {
                "ok": bool(selected),
                "skipped": True,
                "reason": "recovery_cooldown",
                "route": f"{selected[0].name}/{selected[1]}" if selected else None,
                "last_recovered": self._last_recovered_route,
            }

        self._last_recovery_at = now
        results = self.model_health.test_all_parallel(timeout_seconds=12)
        working = [row for row in results if row.get("ok")]
        if not working:
            return {"ok": False, "skipped": False, "reason": "no_working_model", "tested": len(results), "route": None}

        if prefer_fastest:
            working.sort(key=lambda row: (int(row.get("latency_ms") or 10_000), 0 if row.get("free") else 1, str(row.get("provider") or ""), str(row.get("model") or "")))
        else:
            working.sort(key=lambda row: (0 if row.get("free") else 1, int(row.get("latency_ms") or 10_000), str(row.get("provider") or ""), str(row.get("model") or "")))

        best = working[0]
        provider_name = str(best["provider"])
        model_id = str(best["model"])
        route = f"{provider_name}/{model_id}"
        latency = int(best.get("latency_ms") or 0)

        for row in working:
            p, m = str(row.get("provider") or ""), str(row.get("model") or "")
            if p and m:
                self.router._model_cooldown_until.pop(f"{p}:{m}", None)
                self.router._cooldown_until.pop(p, None)
                if hasattr(self.router, "record_probe_latency") and row.get("ok"):
                    self.router.record_probe_latency(p, m, int(row.get("latency_ms") or 0))

        if hasattr(self.router, "prefer_route"):
            self.router.prefer_route(provider_name, model_id, latency)

        persisted = False
        try:
            from src.database.models.ai_model import AIModel
            from src.database.models.ai_provider import AIProvider
            from src.database.session import SessionLocal
            from src.services.ai.model_service import AIModelService

            db = SessionLocal()
            try:
                model_row = (
                    db.query(AIModel)
                    .join(AIProvider, AIProvider.id == AIModel.provider_id)
                    .filter(AIProvider.name == provider_name, AIModel.model_id == model_id, AIModel.is_active.is_(True), AIProvider.is_active.is_(True))
                    .first()
                )
                if model_row is not None:
                    AIModelService(db).set_default(model_row.id)
                    persisted = True
            finally:
                db.close()
        except Exception:
            persisted = False

        self._last_recovered_route = route
        return {
            "ok": True,
            "skipped": False,
            "reason": "recovered",
            "route": route,
            "provider": provider_name,
            "model": model_id,
            "free": bool(best.get("free")),
            "latency_ms": latency,
            "persisted_default": persisted,
            "working_count": len(working),
            "tested": len(results),
            "prefer_fastest": prefer_fastest,
        }

    def _request_model(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": "You are the RahYar senior software engineer. Follow project architecture. Never include secrets. Return concise engineering output."},
            {"role": "user", "content": prompt},
        ]
        attempts = 0
        candidates = self.router._ordered_candidates(self.router.providers())
        try:
            configured_retries = max(0, int(self.settings.AI_AGENT_MAX_RETRIES))
        except (TypeError, ValueError):
            configured_retries = 2
        max_attempts = max(1, min(len(candidates) + configured_retries, 24))
        last_empty_model = ""
        catalog_recovery_attempted = False

        while attempts < max_attempts:
            attempts += 1
            try:
                data = self.router.chat(messages, temperature=0.1, timeout_seconds=self.settings.AI_AGENT_TIMEOUT_SECONDS)
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                if isinstance(content, list):
                    content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict) and part.get("text"))
                content = str(content or "").strip()
                if not content:
                    provider_name = str(data.get("_rahyar_provider") or "")
                    model_name = str(data.get("_rahyar_model") or "")
                    model_key = f"{provider_name}:{model_name}"
                    if model_name and model_key != last_empty_model:
                        self.router._model_cooldown_until[model_key] = time.time() + 60
                        last_empty_model = model_key
                        continue
                    raise AIProviderError("AI provider returned an empty response", retryable=True, retry_after=60, provider=provider_name)
                return content
            except AIProviderError as exc:
                detail = str(exc)
                if exc.retry_after:
                    detail += f" (retry_after={exc.retry_after}s)"
                lowered = str(exc).lower()
                needs_recovery = "cooling down" in lowered or "temporarily unavailable" in lowered or (exc.retryable and attempts >= max(2, max_attempts // 2))
                if needs_recovery and not catalog_recovery_attempted:
                    catalog_recovery_attempted = True
                    try:
                        recovered = self.recover_working_route(force=True, prefer_fastest=True)
                        if recovered.get("ok"):
                            attempts = max(0, attempts - 1)
                            continue
                    except Exception:
                        pass
                if attempts < max_attempts and exc.retryable:
                    continue
                raise AIAgentError(f"AI provider router failed: {detail}") from exc
            except (KeyError, IndexError, TypeError) as exc:
                raise AIAgentError("AI provider returned an unexpected response.") from exc

        if not catalog_recovery_attempted:
            try:
                recovered = self.recover_working_route(force=True, prefer_fastest=True)
                if recovered.get("ok"):
                    data = self.router.chat(messages, temperature=0.1, timeout_seconds=self.settings.AI_AGENT_TIMEOUT_SECONDS)
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")
                    if isinstance(content, list):
                        content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict) and part.get("text"))
                    content = str(content or "").strip()
                    if content:
                        return content
            except Exception:
                pass
        raise AIAgentError("All configured AI models returned no usable output.")

    def test_provider_models(self) -> str:
        self._check_enabled(require_git=False)
        try:
            recovery = self.recover_working_route(force=True, prefer_fastest=True)
            results = self.model_health.test_all_parallel(timeout_seconds=12)
        except AIProviderError as exc:
            raise AIAgentError(str(exc)) from exc
        if not results:
            return "🧪 هیچ provider/model فعالی برای تست پیدا نشد."
        lines = ["🧪 <b>Live AI Model Test (parallel + fastest)</b>", "━━━━━━━━━━━━━━━━━━"]
        available = free_available = 0
        for row in results:
            icon = "🟢" if row["ok"] else "🔴"
            free = "FREE" if row.get("free") else "PAID"
            latency = f"{row.get('latency_ms')}ms"
            if row["ok"]:
                available += 1
                free_available += int(bool(row.get("free")))
                response = str(row.get("response") or "").replace("\n", " ").strip()
                lines.append(f"\n{icon} <b>{row['provider']}</b> / <code>{row['model']}</code> · {free} · {latency}\n   ✅ READY · <code>{response[:180]}</code>")
            else:
                lines.append(f"\n{icon} <b>{row['provider']}</b> / <code>{row['model']}</code> · {free} · {latency}\n   ❌ {str(row.get('status') or 'unknown').upper()}")
        selected = self._selected_candidate()
        selected_text = f"{selected[0].name}/{selected[1]}" if selected else "none"
        lines.extend(["\n━━━━━━━━━━━━━━━━━━", f"🟢 پاسخ‌دهنده: <b>{available}/{len(results)}</b> · 🆓 <b>{free_available}</b>", f"🎯 Route فعال: <code>{selected_text}</code>"])
        if recovery.get("route"):
            lines.append(f"⚡ Fastest pin: <code>{recovery['route']}</code> · {recovery.get('latency_ms')}ms")
        lines.append("ℹ️ مانیتور مداوم در پس‌زمینه همیشه به سریع‌ترین مدل پاسخ‌دهنده سوئیچ می‌کند.")
        return "\n".join(lines)

    def auto_connect_working_model(self) -> str:
        self._check_enabled(require_git=False)
        try:
            result = self.recover_working_route(force=True, prefer_fastest=True)
        except AIProviderError as exc:
            raise AIAgentError(str(exc)) from exc
        if not result.get("ok"):
            return "🔴 <b>اتصال خودکار ناموفق</b>\nهیچ مدلی پاسخ نداد. API key / base URL را در Render چک کنید."
        free_label = "🆓 رایگان" if result.get("free") else "💳 پولی"
        return (
            "🟢 <b>سریع‌ترین مدل وصل شد</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Route: <code>{result.get('route')}</code>\n"
            f"⏱ {result.get('latency_ms')}ms · {free_label}\n"
            f"🧪 سالم: <b>{result.get('working_count')}/{result.get('tested')}</b>\n"
            "مانیتور مداوم این انتخاب را به‌روز نگه می‌دارد."
        )

    def _live_agent_probe(self) -> tuple[str, str]:
        data = self.router.chat(
            [
                {"role": "system", "content": "You are a health-check endpoint for RahYar AI Agent. Reply exactly OK."},
                {"role": "user", "content": "Reply with exactly: OK"},
            ],
            temperature=0,
            max_tokens=8,
            timeout_seconds=min(self.settings.AI_AGENT_TIMEOUT_SECONDS, 20),
        )
        provider = str(data.get("_rahyar_provider") or "")
        model = str(data.get("_rahyar_model") or "")
        if not provider or not model:
            raise AIAgentError("Router returned no active provider/model metadata.")
        return provider, model

    def status(self) -> str:
        self._check_enabled(require_git=False)
        providers = self.router.providers()
        if not providers:
            raise AIAgentError("No AI provider is configured")
        candidates = self.router._ordered_candidates(providers)
        free_count = sum(1 for _, model in candidates if self.router._is_free_model(model))
        route_lines = [f"{p.name}/{m}{' [free]' if self.router._is_free_model(m) else ''}" for p, m in candidates]
        try:
            active_provider, active_model = self._live_agent_probe()
            live = f"{active_provider}/{active_model}"
        except (AIProviderError, AIAgentError) as exc:
            try:
                recovered = self.recover_working_route(force=True, prefer_fastest=True)
                live = f"RECOVERED:{recovered.get('route')}" if recovered.get("ok") else f"FAILED: {str(exc)[:160]}"
            except Exception:
                live = f"FAILED: {str(exc)[:160]}"
        write = self._write_capable()
        lines = [
            f"enabled={self.settings.AI_AGENT_ENABLED}",
            f"model={live}",
            f"api_key_configured={bool(providers)}",
            f"max_retries={self.settings.AI_AGENT_MAX_RETRIES}",
            f"write_mode={'yes' if write else 'no'}",
            f"router_free_candidates={free_count}",
            f"router_candidates={route_lines!r}",
            "auto_recover=enabled",
            "continuous_fastest_probe=enabled",
        ]
        if self._last_recovered_route:
            lines.append(f"last_auto_recovered={self._last_recovered_route}")
        if hasattr(self.router, "latency_snapshot"):
            snap = self.router.latency_snapshot()[:5]
            if snap:
                lines.append(f"latency_top={snap!r}")
        return "\n".join(lines)
