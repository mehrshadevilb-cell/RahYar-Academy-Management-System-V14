from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from src.core.config.settings import get_settings


class AIClient:
    """Small OpenAI-compatible client with provider/transport guardrails.

    The client is configured lazily so a missing optional AI environment does
    not prevent the Telegram bot from starting.
    """

    MAX_PROMPT_CHARS = 16_000

    def __init__(self) -> None:
        self.api_key: str | None = None
        self.base_url = ""
        self.model = ""
        self.timeout = 180
        self._refresh()

    def _refresh(self) -> None:
        settings = get_settings()
        self.api_key = settings.effective_ai_api_key
        self.base_url = settings.effective_ai_base_url.rstrip("/")
        self.model = settings.effective_ai_model
        self.timeout = min(max(settings.AI_AGENT_TIMEOUT_SECONDS, 5), 180)
        self._validate_endpoint()

    def _validate_endpoint(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https":
            raise RuntimeError("AI provider endpoint must use HTTPS")
        if not parsed.hostname:
            raise RuntimeError("AI provider endpoint is invalid")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("AI API key is not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "RahYar-AIClient/1.0",
        }

    async def chat(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self._refresh()
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("AI prompt cannot be empty")
        if len(prompt) > self.MAX_PROMPT_CHARS:
            raise ValueError("AI prompt is too large")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise RuntimeError("AI provider returned an invalid response")
            return data
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"AI provider returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("AI provider is unreachable") from exc
        except TimeoutError as exc:
            raise RuntimeError("AI provider request timed out") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("AI provider returned invalid JSON") from exc


ai_client = AIClient()
