from __future__ import annotations

import time

from src.ai.provider_router import AIProviderError, AIProviderRouter
from src.ai.shared_router import get_shared_router
from src.services.ai_agent_service import AIAgentError, AIAgentService
from src.services.provider_model_health_service import ProviderModelHealthService


class RoutedAIAgentService(AIAgentService):
    """AI Agent service using the shared latency-aware provider pool."""

    def __init__(self) -> None:
        super().__init__()
        self.router = get_shared_router()
        self.model_health = ProviderModelHealthService(self.router)

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
                content = ""
                if isinstance(data, dict):
                    choices = data.get("choices") or []
                    if choices and isinstance(choices[0], dict):
                        message = choices[0].get("message") or {}
                        raw = message.get("content") if isinstance(message, dict) else ""
                        if isinstance(raw, list):
                            content = " ".join(
                                str(part.get("text", ""))
                                for part in raw
                                if isinstance(part, dict) and part.get("text")
                            )
                        else:
                            content = str(raw or "")
                    if not content:
                        for ptype in ("openai_compatible", "google", "anthropic"):
                            content = AIProviderRouter._extract_text(data, ptype)
                            if content:
                                break
                content = str(content or "").strip()

                if not content:
                    provider_name = str(data.get("_rahyar_provider") or "")
                    model_name = str(data.get("_rahyar_model") or "")
                    model_key = f"{provider_name}:{model_name}"
                    if model_name and model_key != last_empty_model:
                        if hasattr(self.router, "_persist_model_cooldown"):
                            self.router._persist_model_cooldown(model_key, 60)
                        else:
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
            "🔎 shared pool برای Agent + Chat Assistant + Web",
        ]
        available = free_available = discovered_models = 0
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
                if row.get("retry_after"):
                    detail += f" · retry {row['retry_after']}s"
                lines.append(
                    f"\n{icon} <b>{row['provider']}</b> / <code>{row['model']}</code> · {free} · {latency}\n"
                    f"   ❌ <b>{detail}</b> · {source}"
                )

        selected = self._selected_candidate()
        selected_text = f"{selected[0].name}/{selected[1]}" if selected else "none"
        cool = self.router.cooldown_snapshot()
        lines.extend(
            [
                "\n━━━━━━━━━━━━━━━━━━",
                f"📡 Providerها: <b>{len(providers)}</b>",
                f"🔎 کشف‌شده از API: <b>{discovered_models}</b>",
                f"🧪 تست‌شده: <b>{len(results)}</b>",
                f"🟢 آماده: <b>{available}/{len(results)}</b>",
                f"🆓 Free: <b>{free_available}</b>",
                f"🧊 Cooldown: <b>{len(cool)}</b>",
                f"🎯 Route: <code>{selected_text}</code>",
                "ℹ️ Failover: Free→Paid · 404→1h · Redis shared cooldown",
            ]
        )
        return "\n".join(lines)

    def _live_agent_probe(self) -> tuple[str, str]:
        data = self.router.chat(
            [
                {
                    "role": "system",
                    "content": "You are a health-check endpoint for RahYar AI Agent. Reply exactly OK.",
                },
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
        free_count = sum(
            1 for provider, model in candidates if self.router._is_free_model(model)
        )
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
            f"cooldown_active={len(self.router.cooldown_snapshot())}",
            "agent_operations=shared_router(Planner,Audit,Debug,Assistant,Fix,Feature,ChatAssistant,Web)",
        ]
        if self._has_git():
            try:
                lines.extend(
                    [
                        f"branch={self._git('branch', '--show-current')}",
                        f"head={self._git('rev-parse', '--short', 'HEAD')}",
                        f"locked={self._lock_path().exists()}",
                    ]
                )
            except AIAgentError as exc:
                lines.append(f"git_error={exc}")
        elif self.settings.github_write_ready:
            lines.append("note=Online write: clone on demand to AI_AGENT_WORK_DIR, push ai/* + PR")
        else:
            lines.append("note=برای نوشتن کد: AI_AGENT_WRITE_ENABLED + GITHUB_TOKEN + GITHUB_REPO")
        return "\n".join(lines)
