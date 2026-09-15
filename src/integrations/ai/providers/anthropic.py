from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from src.integrations.ai.base import BaseAIProvider


class AnthropicProvider(BaseAIProvider):
    def _headers(self) -> dict[str, str]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.extra_config.get("anthropic_version", "2023-06-01"),
            "content-type": "application/json",
        }
        headers.update(self.extra_config.get("headers", {}))
        return headers

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/models", headers=self._headers())
            response.raise_for_status()
            payload = response.json()
        return [{"id": x.get("id"), "display_name": x.get("display_name") or x.get("id"), "raw_metadata": x} for x in payload.get("data", []) if x.get("id")]

    async def chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        system = kwargs.pop("system", None)
        body = {"model": model, "messages": messages, **kwargs}
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/messages", headers=self._headers(), json=body)
            response.raise_for_status()
            return response.json()

    async def stream_chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        system = kwargs.pop("system", None)
        body = {"model": model, "messages": messages, "stream": True, **kwargs}
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", f"{self.base_url}/messages", headers=self._headers(), json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        yield line[5:].strip()
