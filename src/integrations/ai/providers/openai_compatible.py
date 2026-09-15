from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from src.integrations.ai.base import BaseAIProvider


class OpenAICompatibleProvider(BaseAIProvider):
    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        headers.update(self.extra_config.get("headers", {}))
        return headers

    def _timeout(self) -> float:
        return float(self.extra_config.get("timeout", 30.0))

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.get(f"{self.base_url}/models", headers=self._headers())
            response.raise_for_status()
            payload = response.json()
        return [self._normalize_model(item) for item in payload.get("data", []) if item.get("id")]

    async def chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        body = {"model": model, "messages": messages, **kwargs}
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            )
            response.raise_for_status()
            return response.json()

    async def stream_chat_completion(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        body = {"model": model, "messages": messages, **kwargs, "stream": True}
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body
            ) as response:
                response.raise_for_status()
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
            "display_name": item.get("name") or item.get("id"),
            "context_window": item.get("context_window") or item.get("context_length"),
            "max_output_tokens": item.get("max_output_tokens"),
            "supports_vision": bool(item.get("supports_vision", False)),
            "supports_tools": bool(item.get("supports_tools", False)),
            "supports_streaming": bool(item.get("supports_streaming", True)),
            "pricing_input": item.get("pricing_input"),
            "pricing_output": item.get("pricing_output"),
            "raw_metadata": metadata,
        }
