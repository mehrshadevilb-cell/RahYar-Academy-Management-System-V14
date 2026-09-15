from __future__ import annotations

import time

from src.ai.latency_aware_provider_router import LatencyAwareAIProviderRouter
from src.ai.provider_router import AIProviderError, AIProviderRouter
from src.services.ai_agent_service import AIAgentError, AIAgentService
from src.services.provider_model_health_service import ProviderModelHealthService


class RoutedAIAgentService(AIAgentService):
    """AI Agent service using one live DB/env provider pool for every agent operation."""

    def __init__(self) -> None:
        super().__init__()
        self.router = LatencyAwareAIProviderRouter()
        self.model_health = ProviderModelHealthService(self.router)

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
        # Candidate count is not a retry budget: a single configured model
        # still needs bounded recovery from transient 5xx/timeout failures.
        max_attempts = max(1, min(len(candidates) + configured_retries, 24))
        last_empty_model = ""
        cooldown_recovery_attempted = False

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
                if (
                    exc.retryable
                    and not cooldown_recovery_attempted
                    and "cooling down" in str(exc).lower()
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

        raise AIAgentError("All configured AI models returned no usable output.")

    def test_provider_models(self) -> str:
        """Discover and live-test every model in the same pool used by agent requests."""
        self._check_enabled(require_git=False)
        try:
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
        lines.extend([
            "\n━━━━━━━━━━━━━━━━━━",
            f"📡 Providerهای بررسی‌شده: <b>{len(providers)}</b>",
            f"🔎 مدل‌های کشف‌شده از API: <b>{discovered_models}</b>",
            f"🧪 کل مدل‌های تست‌شده: <b>{len(results)}</b>",
            f"🟢 مدل‌های واقعاً پاسخ‌دهنده: <b>{available}/{len(results)}</b>",
            f"🆓 Free آماده: <b>{free_available}</b>",
            f"🎯 Route انتخابی Agent: <code>{selected_text}</code>",
            "ℹ️ اگر route فعلی از کار بیفتد، router در همان درخواست به مدل بعدی طبق اولویت Free→Paid failover می‌کند؛ این انتخاب برای همه بخش‌های Agent مشترک است.",
        ])
        return "\n".join(lines)

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
        ]
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
