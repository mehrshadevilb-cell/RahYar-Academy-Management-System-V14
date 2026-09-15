from __future__ import annotations

from src.ai.provider_router import AIProviderError, AIProviderRouter
from src.services.ai_agent_service import AIAgentError, AIAgentService


class RoutedAIAgentService(AIAgentService):
    """AI Agent service using the DB-backed free-first provider router."""

    def __init__(self) -> None:
        super().__init__()
        self.router = AIProviderRouter()

    def _api_key(self) -> str:
        if self.router.providers():
            return "router-managed"
        return super()._api_key()

    def _base_url(self) -> str:
        providers = self.router.providers()
        if providers:
            return providers[0].base_url
        return super()._base_url()

    def _model(self) -> str:
        providers = self.router.providers()
        if providers:
            return providers[0].model
        return super()._model()

    def _request_model(self, prompt: str) -> str:
        try:
            data = self.router.chat(
                [
                    {"role": "system", "content": "You are the RahYar senior software engineer. Follow project architecture. Never include secrets. Return concise engineering output."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                timeout_seconds=self.settings.AI_AGENT_TIMEOUT_SECONDS,
            )
            return str(data["choices"][0]["message"]["content"])
        except AIProviderError as exc:
            detail = str(exc)
            if exc.retry_after:
                detail += f" (retry_after={exc.retry_after}s)"
            raise AIAgentError(f"AI provider router failed: {detail}") from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise AIAgentError("AI provider returned an unexpected response.") from exc

    def test_provider_models(self) -> str:
        """Run an explicit live health check against every configured model."""
        self._check_enabled(require_git=False)
        try:
            results = self.router.test_models(timeout_seconds=15)
        except AIProviderError as exc:
            raise AIAgentError(str(exc)) from exc
        if not results:
            return "🧪 هیچ مدل فعالی برای تست پیدا نشد."

        lines = ["🧪 <b>Live AI Model Test</b>", "━━━━━━━━━━━━━━━━━━", "🔎 هر ردیف با یک درخواست واقعی تست شده است."]
        available = 0
        free_available = 0
        for row in results:
            icon = "🟢" if row["ok"] else "🔴"
            free = "FREE" if row["free"] else "PAID"
            latency = f"{row['latency_ms']}ms"
            if row["ok"]:
                available += 1
                free_available += int(row["free"])
                response = str(row.get("response") or "").replace("\n", " ").strip()
                lines.append(
                    f"\n{icon} <b>{row['provider']}</b> / <code>{row['model']}</code> · {free} · {latency}\n"
                    f"   ✅ <b>READY</b> · پاسخ: <code>{response[:220]}</code>"
                )
            else:
                detail = str(row.get("status") or "unknown").upper()
                retry_after = row.get("retry_after")
                if retry_after:
                    detail += f" · retry {retry_after}s"
                lines.append(
                    f"\n{icon} <b>{row['provider']}</b> / <code>{row['model']}</code> · {free} · {latency}\n"
                    f"   ❌ <b>{detail}</b>"
                )

        lines.extend([
            "\n━━━━━━━━━━━━━━━━━━",
            f"🟢 مدل‌های واقعاً پاسخ‌دهنده: <b>{available}/{len(results)}</b>",
            f"🆓 Free آماده: <b>{free_available}</b>",
            "ℹ️ تست live است و cooldown قبلی را نادیده می‌گیرد؛ هیچ key یا endpointی نمایش داده نمی‌شود.",
        ])
        return "\n".join(lines)

    def status(self) -> str:
        """Return sanitized health for the same provider pool used by requests."""
        self._check_enabled(require_git=False)
        providers = self.router.providers()
        if not providers:
            raise AIAgentError("No AI provider is configured")

        candidates = self.router._ordered_candidates(providers)
        free_count = sum(1 for provider, model in candidates if self.router._is_free_model(model))
        route_lines = [f"{provider.name}/{model}{' [free]' if self.router._is_free_model(model) else ''}" for provider, model in candidates]
        write = self._write_capable()
        lines = [
            f"enabled={self.settings.AI_AGENT_ENABLED}",
            f"api_key_configured={bool(providers)}",
            f"model={candidates[0][1] if candidates else self._model()}",
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
        ]
        if self._has_git():
            try:
                lines.extend([f"branch={self._git('branch', '--show-current')}", f"head={self._git('rev-parse', '--short', 'HEAD')}", f"locked={self._lock_path().exists()}"])
            except AIAgentError as exc:
                lines.append(f"git_error={exc}")
        elif self.settings.github_write_ready:
            lines.append("note=Online write: clone on demand to AI_AGENT_WORK_DIR, push ai/* + PR")
        else:
            lines.append("note=برای نوشتن کد: AI_AGENT_WRITE_ENABLED + GITHUB_TOKEN + GITHUB_REPO")
        lines.append("provider_ping=deferred_to_router_request")
        return "\n".join(lines)
