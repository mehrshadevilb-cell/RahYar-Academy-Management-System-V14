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
        # Do not let legacy AI_API_KEY decide which agent route is active.
        # The router is the single source of truth for the whole agent.
        if self.router.providers():
            return "router-managed"
        return super()._api_key()

    def _selected_candidate(self):
        """Return the same priority-ordered candidate used by agent requests.

        This is informational/configuration selection only. Actual model calls
        always go through router.chat(), which can fail over again at request
        time if this candidate is unhealthy.
        """
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

    def recover_working_route(self, *, force: bool = False) -> dict[str, Any]:
        """Live-test every model, clear healthy cooldowns, and pin a working default.

        When the current model is cut/rate-limited, the bot must find a model that
        still answers and prefer it for subsequent Agent/Chat operations.

        Priority: known free models that answer → any answering model.
        """
        now = time.time()
        # Avoid hammering every provider on rapid consecutive failures.
        if not force and self._last_recovery_at and now - self._last_recovery_at < 45:
            selected = self._selected_candidate()
            return {
                "ok": bool(selected),
                "skipped": True,
                "reason": "recovery_cooldown",
                "route": f"{selected[0].name}/{selected[1]}" if selected else None,
                "last_recovered": self._last_recovered_route,
            }

        self._last_recovery_at = now
        results = self.model_health.test_all(timeout_seconds=15)
        working = [row for row in results if row.get("ok")]
        if not working:
            return {
                "ok": False,
                "skipped": False,
                "reason": "no_working_model",
                "tested": len(results),
                "route": None,
            }

        # Free-first among models that actually answered.
        working.sort(
            key=lambda row: (
                0 if row.get("free") else 1,
                int(row.get("latency_ms") or 10_000),
                str(row.get("provider") or ""),
                str(row.get("model") or ""),
            )
        )
        best = working[0]
        provider_name = str(best["provider"])
        model_id = str(best["model"])
        route = f"{provider_name}/{model_id}"

        # Clear process-local cooldowns for every healthy model so the router
        # can use them immediately on the next request.
        for row in working:
            p = str(row.get("provider") or "")
            m = str(row.get("model") or "")
            if p and m:
                self.router._model_cooldown_until.pop(f"{p}:{m}", None)
                self.router._cooldown_until.pop(p, None)

        # Persist default in DB when the model is known to the catalog so the
        # next process / request prefers this route without re-discovery.
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
                    .filter(
                        AIProvider.name == provider_name,
                        AIModel.model_id == model_id,
                        AIModel.is_active.is_(True),
                        AIProvider.is_active.is_(True),
                    )
                    .first()
                )
                if model_row is not None:
                    AIModelService(db).set_default(model_row.id)
                    persisted = True
            finally:
                db.close()
        except Exception:
            # Recovery must not fail because persistence is unavailable
            # (e.g. SQLite lock or missing tables on a fresh deploy).
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
            "latency_ms": best.get("latency_ms"),
            "persisted_default": persisted,
            "working_count": len(working),
            "tested": len(results),
        }

    def _request_model(self, prompt: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the RahYar senior software engineer. "
                    "Follow project architecture. Never include secrets. "
                    "Return concise engineering output."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        attempts = 0
        candidates = self.router._ordered_candidates(self.router.providers())
        try:
            configured_retries = max(0, int(self.settings.AI_AGENT_MAX_RETRIES))
        except (TypeError, ValueError):
            configured_retries = 2
        # Candidate count is not a retry budget: a single configured model
        # still needs bounded recovery from transient 5xx/timeout failures.
        max_attempts = max(1, min(len(candidates) + configured_retries, 24))
        last_empty_model = ""
        cooldown_recovery_attempted = False
        catalog_recovery_attempted = False

        while attempts < max_attempts:
            attempts += 1
            try:
                data = self.router.chat(
                    messages,
                    temperature=0.1,
                    timeout_seconds=self.settings.AI_AGENT_TIMEOUT_SECONDS,
                )
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                if isinstance(content, list):
                    content = " ".join(
                        str(part.get("text", ""))
                        for part in content
                        if isinstance(part, dict) and part.get("text")
                    )
                content = str(content or "").strip()

                if not content:
                    provider_name = str(data.get("_rahyar_provider") or "")
                    model_name = str(data.get("_rahyar_model") or "")
                    model_key = f"{provider_name}:{model_name}"
                    if model_name and model_key != last_empty_model:
                        self.router._model_cooldown_until[model_key] = time.time() + 60
                        last_empty_model = model_key
                        continue
                    raise AIProviderError(
                        "AI provider returned an empty response",
                        retryable=True,
                        retry_after=60,
                        provider=provider_name,
                    )

                return content
            except AIProviderError as exc:
                detail = str(exc)
                if exc.retry_after:
                    detail += f" (retry_after={exc.retry_after}s)"
                lowered = str(exc).lower()
                needs_recovery = (
                    "cooling down" in lowered
                    or "temporarily unavailable" in lowered
                    or "no usable output" in lowered
                    or (exc.retryable and attempts >= max(2, max_attempts // 2))
                )
                if needs_recovery and not catalog_recovery_attempted:
                    catalog_recovery_attempted = True
                    try:
                        recovered = self.recover_working_route(force=True)
                        if recovered.get("ok"):
                            # Give the loop another full budget against the
                            # newly healthy route without counting this as a
                            # failed user-visible attempt.
                            attempts = max(0, attempts - 1)
                            continue
                    except (AIProviderError, OSError, TimeoutError, ValueError, TypeError):
                        pass
                if (
                    exc.retryable
                    and not cooldown_recovery_attempted
                    and "cooling down" in lowered
                ):
                    cooldown_recovery_attempted = True
                    # A health probe uses the exact same router instance and
                    # clears stale cooldowns for routes that answer now.
                    try:
                        recovered = self.model_health.test_all(
                            timeout_seconds=min(self.settings.AI_AGENT_TIMEOUT_SECONDS, 15)
                        )
                        if any(bool(row.get("ok")) for row in recovered):
                            attempts -= 1
                            continue
                    except (AIProviderError, OSError, TimeoutError, ValueError, TypeError):
                        pass
                if attempts < max_attempts and exc.retryable:
                    continue
                raise AIAgentError(f"AI provider router failed: {detail}") from exc
            except (KeyError, IndexError, TypeError) as exc:
                raise AIAgentError("AI provider returned an unexpected response.") from exc

        # Final attempt: force catalog recovery then one last chat.
        if not catalog_recovery_attempted:
            try:
                recovered = self.recover_working_route(force=True)
                if recovered.get("ok"):
                    data = self.router.chat(
                        messages,
                        temperature=0.1,
                        timeout_seconds=self.settings.AI_AGENT_TIMEOUT_SECONDS,
                    )
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")
                    if isinstance(content, list):
                        content = " ".join(
                            str(part.get("text", ""))
                            for part in content
                            if isinstance(part, dict) and part.get("text")
                        )
                    content = str(content or "").strip()
                    if content:
                        return content
            except Exception:
                pass

        raise AIAgentError("All configured AI models returned no usable output.")

    def test_provider_models(self) -> str:
        """Discover and live-test every model in the same pool used by agent requests."""
        self._check_enabled(require_git=False)
        try:
            recovery = self.recover_working_route(force=True)
            results = self.model_health.test_all(timeout_seconds=15)
        except AIProviderError as exc:
            raise AIAgentError(str(exc)) from exc
        if not results:
            return "🧪 هیچ provider/model فعالی برای تست پیدا نشد."

        lines = [
            "🧪 <b>Live AI Model Test</b>",
            "━━━━━━━━━━━━━━━━━━",
            "🔎 همان provider pool که Agent برای Planner/Audit/Debug/Fix/Feature استفاده می‌کند live-test می‌شود.",
        ]
        available = 0
        free_available = 0
        discovered_models = 0
        providers = sorted({str(row["provider"]) for row in results})
        for row in results:
            icon = "🟢" if row["ok"] else "🔴"
            free = "FREE" if row["free"] else "PAID"
            latency = f"{row['latency_ms']}ms"
            source = "API catalog" if row.get("discovered") else "configured fallback"
            if row.get("discovered"):
                discovered_models += 1
            if row["ok"]:
                available += 1
                free_available += int(row["free"])
                response = str(row.get("response") or "").replace("\n", " ").strip()
                lines.append(
                    f"\n{icon} <b>{row['provider']}</b> / <code>{row['model']}</code> · {free} · {latency}\n"
                    f"   ✅ <b>READY</b> · {source} · پاسخ: <code>{response[:220]}</code>"
                )
            else:
                detail = str(row.get("status") or "unknown").upper()
                retry_after = row.get("retry_after")
                if retry_after:
                    detail += f" · retry {retry_after}s"
                lines.append(
                    f"\n{icon} <b>{row['provider']}</b> / <code>{row['model']}</code> · {free} · {latency}\n"
                    f"   ❌ <b>{detail}</b> · {source}"
                )

        selected = self._selected_candidate()
        selected_text = f"{selected[0].name}/{selected[1]}" if selected else "none"
        recovered_route = recovery.get("route") if isinstance(recovery, dict) else None
        lines.extend([
            "\n━━━━━━━━━━━━━━━━━━",
            f"📡 Providerهای بررسی‌شده: <b>{len(providers)}</b>",
            f"🔎 مدل‌های کشف‌شده از API: <b>{discovered_models}</b>",
            f"🧪 کل مدل‌های تست‌شده: <b>{len(results)}</b>",
            f"🟢 مدل‌های واقعاً پاسخ‌دهنده: <b>{available}/{len(results)}</b>",
            f"🆓 Free آماده: <b>{free_available}</b>",
            f"🎯 Route انتخابی Agent: <code>{selected_text}</code>",
        ])
        if recovered_route:
            persist = recovery.get("persisted_default")
            lines.append(
                f"♻️ Auto-recover: <code>{recovered_route}</code>"
                + (" · default ذخیره شد" if persist else " · default فقط در حافظه")
            )
        lines.append(
            "ℹ️ اگر route فعلی از کار بیفتد، router در همان درخواست به مدل بعدی طبق اولویت Free→Paid failover می‌کند؛ "
            "در صورت قطع کامل، بازیابی خودکار مدل سالم را پیدا و وصل می‌کند."
        )
        return "\n".join(lines)

    def auto_connect_working_model(self) -> str:
        """Owner-facing recovery: find a working model and connect the agent to it."""
        self._check_enabled(require_git=False)
        try:
            result = self.recover_working_route(force=True)
        except AIProviderError as exc:
            raise AIAgentError(str(exc)) from exc

        if not result.get("ok"):
            return (
                "🔴 <b>اتصال خودکار ناموفق</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "هیچ مدلی در حال حاضر پاسخ نداد.\n"
                "کلید API و base URL را در Render بررسی کنید، سپس دوباره «Test Models» بزنید."
            )

        free_label = "🆓 رایگان" if result.get("free") else "💳 پولی"
        persist = (
            "✅ default در دیتابیس ذخیره شد"
            if result.get("persisted_default")
            else "⚠️ فقط در حافظهٔ runtime (جدول مدل در DB نبود)"
        )
        latency = result.get("latency_ms")
        latency_text = f"{latency}ms" if latency is not None else "—"
        return (
            "🟢 <b>اتصال خودکار موفق</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Route فعال: <code>{result.get('route')}</code>\n"
            f"🏷 نوع: {free_label}\n"
            f"⏱ Latency: <code>{latency_text}</code>\n"
            f"💾 {persist}\n"
            f"🧪 تست‌شده: <b>{result.get('tested', 0)}</b> · سالم: <b>{result.get('working_count', 0)}</b>\n\n"
            "از این لحظه Planner / Audit / Debug / Fix / Feature از همین مدل استفاده می‌کنند. "
            "اگر دوباره قطع شود، Agent خودش مدل سالم بعدی را پیدا می‌کند."
        )

    def _live_agent_probe(self) -> tuple[str, str]:
        """Perform one real routed request and return the route that answered."""
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
        """Return health for the exact provider pool used by every agent operation."""
        self._check_enabled(require_git=False)
        providers = self.router.providers()
        if not providers:
            raise AIAgentError("No AI provider is configured")

        candidates = self.router._ordered_candidates(providers)
        free_count = sum(1 for provider, model in candidates if self.router._is_free_model(model))
        route_lines = [
            f"{provider.name}/{model}{' [free]' if self.router._is_free_model(model) else ''}"
            for provider, model in candidates
        ]
        try:
            active_provider, active_model = self._live_agent_probe()
            live = f"{active_provider}/{active_model}"
        except (AIProviderError, AIAgentError) as exc:
            # Automatic recovery when the status probe fails.
            try:
                recovered = self.recover_working_route(force=True)
                if recovered.get("ok"):
                    live = f"RECOVERED:{recovered.get('route')}"
                else:
                    live = f"FAILED: {str(exc)[:180]}"
            except Exception:
                live = f"FAILED: {str(exc)[:180]}"
        write = self._write_capable()
        lines = [
            f"enabled={self.settings.AI_AGENT_ENABLED}",
            f"api_key_configured={bool(providers)}",
            f"model={live}",
            f"base_url=hidden ({len(providers)} provider route(s))",
            f"max_retries={self.settings.AI_AGENT_MAX_RETRIES}",
            f"repo={self.repo}",
            f"git_available={self._has_git()}",
            f"github_write_ready={self.settings.github_write_ready}",
            f"write_mode={'yes' if write else 'no (status/analyze only)'}",
            f"chat_assistant_enabled={self.settings.CHAT_ASSISTANT_ENABLED}",
            f"chat_key_configured={bool(self.settings.effective_chat_api_key)}",
            f"router_free_candidates={free_count}",
            f"router_candidates={route_lines!r}",
            "agent_operations=shared_router(Planner,Audit,Debug,Assistant,Fix,Feature,Refactor,Tests)",
            "auto_recover=enabled (live-test → free-first → pin default → clear cooldown)",
        ]
        if self._last_recovered_route:
            lines.append(f"last_auto_recovered={self._last_recovered_route}")
        if self._has_git():
            try:
                lines.extend([
                    f"branch={self._git('branch', '--show-current')}",
                    f"head={self._git('rev-parse', '--short', 'HEAD')}",
                    f"locked={self._lock_path().exists()}",
                ])
            except AIAgentError as exc:
                lines.append(f"git_error={exc}")
        elif self.settings.github_write_ready:
            lines.append("note=Online write: clone on demand to AI_AGENT_WORK_DIR, push ai/* + PR")
        else:
            lines.append("note=برای نوشتن کد: AI_AGENT_WRITE_ENABLED + GITHUB_TOKEN + GITHUB_REPO")
        return "\n".join(lines)
