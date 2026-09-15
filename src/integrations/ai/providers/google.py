from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from src.integrations.ai.base import BaseAIProvider


class GoogleProvider(BaseAIProvider):
    def _url(self, model: str) -> str:
        return f"{self.base_url}/models/{model}:generateContent"

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/models", params={"key": self.api_key})
            response.raise_for_status()
            payload = response.json()
        result = []
        for item in payload.get("models", []):
            model_id = item.get("name", "").removeprefix("models/")
            if model_id:
                result.append({"id": model_id, "display_name": item.get("displayName") or model_id, "raw_metadata": item})
        return result

    async def chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        contents = [{"role": "user" if m.get("role") == "user" else "model", "parts": [{"text": str(m.get("content", ""))}]} for m in messages]
        body = {"contents": contents}
        if kwargs:
            body["generationConfig"] = kwargs
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._url(model), params={"key": self.api_key}, json=body)
            response.raise_for_status()
            return response.json()

    async def stream_chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        contents = [{"role": "user" if m.get("role") == "user" else "model", "parts": [{"text": str(m.get("content", ""))}]} for m in messages]
        body = {"contents": contents}
        if kwargs:
            body["generationConfig"] = kwargs
        url = f"{self.base_url}/models/{model}:streamGenerateContent"
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, params={"key": self.api_key, "alt": "sse"}, json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        yield line[5:].strip()
