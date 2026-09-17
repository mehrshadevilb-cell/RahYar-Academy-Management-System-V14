from __future__ import annotations

import re
from typing import Any, AsyncIterator

import httpx

from src.integrations.ai.base import BaseAIProvider


class OpenAICompatibleProvider(BaseAIProvider):
    def _headers(self) -> dict[str, str]:
        auth_scheme = str(self.extra_config.get("auth_scheme", "bearer")).lower()
        authorization = self.api_key if auth_scheme == "raw" else f"Bearer {self.api_key}"
        headers = {"Authorization": authorization, "Content-Type": "application/json"}
        headers.update(self.extra_config.get("headers", {}))
        return headers

    def _timeout(self) -> float:
        return float(self.extra_config.get("timeout", 30.0))

    @staticmethod
    def _safe_error_body(response: httpx.Response, limit: int = 1200) -> str:
        """Return a short upstream error body without leaking credentials."""
        text = (response.text or "").strip()
        if not text:
            return "<empty response body>"
        text = re.sub(
            r'(?i)("?(?:api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|token|secret|password)"?\s*[:=]\s*")([^"\n]+)(")',
            r'\1[REDACTED]\3',
            text,
        )
        return text[:limit]

    async def _check_discovery_auth(self, client: httpx.AsyncClient) -> str | None:
        """Optionally verify provider auth through a separate health endpoint."""
        health_url = str(self.extra_config.get("discovery_health_url", "")).strip()
        if not health_url:
            return None

        try:
            response = await client.get(health_url, headers=self._headers())
        except httpx.HTTPError as exc:
            return f"health-check request failed: {exc}"

        if response.is_success:
            return "authentication accepted by provider health endpoint"
        if response.status_code in (401, 403):
            return f"authentication rejected by provider health endpoint: HTTP {response.status_code}: {self._safe_error_body(response)}"
        return f"provider health endpoint returned HTTP {response.status_code}: {self._safe_error_body(response)}"

    async def list_models(self) -> list[dict[str, Any]]:
        models_url = str(self.extra_config.get("models_url", "")).strip()
        if not models_url:
            models_url = f"{self.base_url}/models"

        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.get(models_url, headers=self._headers())
            if response.is_error:
                detail = self._safe_error_body(response)
                if response.status_code >= 500:
                    auth_status = await self._check_discovery_auth(client)
                    if auth_status:
                        detail = f"{detail}; discovery-auth check: {auth_status}"
                raise RuntimeError(
                    f"AI model discovery failed: HTTP {response.status_code} "
                    f"from {models_url}: {detail}"
                )
            payload = response.json()

        models_key = str(self.extra_config.get("models_key", "data"))
        raw_models: Any = payload.get(models_key, []) if isinstance(payload, dict) else []

        # Bytez documents `output` as an array, but tolerate equivalent nested
        # response shapes so discovery does not break when the API adds a wrapper.
        if isinstance(raw_models, dict):
            for key in ("models", "data", "items", "results", "output"):
                candidate = raw_models.get(key)
                if isinstance(candidate, list):
                    raw_models = candidate
                    break

        if not isinstance(raw_models, list):
            return []

        model_id_key = str(self.extra_config.get("model_id_key", "id"))
        normalized: list[dict[str, Any]] = []
        for item in raw_models:
            if isinstance(item, str):
                model_id = item.strip()
                if model_id:
                    normalized.append({"model_id": model_id, "display_name": model_id, "raw_metadata": {}})
                continue
            if not isinstance(item, dict):
                continue

            model_id = (
                item.get(model_id_key)
                or item.get("modelId")
                or item.get("model_id")
                or item.get("id")
                or item.get("model")
                or item.get("name")
            )
            if not model_id:
                continue

            normalized.append(self._normalize_model({**item, "id": str(model_id)}))
        return normalized

    async def chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        body = {"model": model, "messages": messages, **kwargs}
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            )
            if response.is_error:
                detail = self._safe_error_body(response)
                raise RuntimeError(
                    f"AI chat request failed: HTTP {response.status_code} "
                    f"from {self.base_url}/chat/completions: {detail}"
                )
            return response.json()

    async def stream_chat_completion(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        body = {"model": model, "messages": messages, **kwargs, "stream": True}
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            ) as response:
                if response.is_error:
                    detail = self._safe_error_body(response)
                    raise RuntimeError(
                        f"AI streaming request failed: HTTP {response.status_code} "
                        f"from {self.base_url}/chat/completions: {detail}"
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = __import__("json").loads(data)
                    except ValueError:
                        continue
                    for choice in chunk.get("choices", []):
                        content = (choice.get("delta") or {}).get("content")
                        if content:
                            yield content

    @staticmethod
    def _normalize_model(item: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(item)
        return {
            "model_id": item["id"],
            "display_name": item.get("name") or item.get("model_name") or item.get("id"),
            "context_window": item.get("context_window") or item.get("context_length") or item.get("contextLength"),
            "max_output_tokens": item.get("max_output_tokens") or item.get("maxOutputTokens"),
            "supports_vision": bool(item.get("supports_vision", item.get("vision", False))),
            "supports_tools": bool(item.get("supports_tools", item.get("tools", False))),
            "supports_streaming": bool(item.get("supports_streaming", True)),
            "pricing_input": item.get("pricing_input") or item.get("input_price"),
            "pricing_output": item.get("pricing_output") or item.get("output_price"),
            "raw_metadata": metadata,
        }
