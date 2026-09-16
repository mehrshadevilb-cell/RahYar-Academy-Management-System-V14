from __future__ import annotations

from src.ai.shared_router import get_shared_router


def wire_chat_assistant_shared_router() -> None:
    """Point ChatAssistantService at the same free-first failover pool as Agent."""
    from src.ai.provider_router import AIProviderError, AIProviderRouter
    from src.services.chat_assistant_service import ChatAssistantError, ChatAssistantService

    _orig_init = ChatAssistantService.__init__

    def _init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        self.router = get_shared_router()

    ChatAssistantService.__init__ = _init

    def _request_model(self, messages, max_tokens=700):
        try:
            data = self.router.chat(
                messages,
                temperature=0.3,
                max_tokens=max_tokens,
                timeout_seconds=self.settings.CHAT_ASSISTANT_TIMEOUT_SECONDS,
            )
            content = ""
            if isinstance(data, dict):
                choices = data.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message") or {}
                    raw = msg.get("content") if isinstance(msg, dict) else ""
                    if isinstance(raw, list):
                        content = " ".join(
                            str(p.get("text", ""))
                            for p in raw
                            if isinstance(p, dict) and p.get("text")
                        )
                    else:
                        content = str(raw or "")
                if not str(content).strip():
                    for ptype in ("openai_compatible", "google", "anthropic"):
                        extracted = AIProviderRouter._extract_text(data, ptype)
                        if extracted:
                            content = extracted
                            break
            content = str(content or "").strip()
            if not content:
                raise AIProviderError("empty", retryable=True, retry_after=30)
            return content
        except AIProviderError as exc:
            if exc.retryable:
                raise ChatAssistantError(
                    "provider_rate_limited" if exc.retry_after else "provider_unavailable"
                ) from exc
            raise ChatAssistantError("provider_unavailable") from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatAssistantError("provider_unavailable") from exc

    ChatAssistantService._request_model = _request_model
