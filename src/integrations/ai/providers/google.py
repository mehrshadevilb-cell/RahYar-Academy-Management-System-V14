from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from src.integrations.ai.base import BaseAIProvider


class GoogleProvider(BaseAIProvider):
    def _url(self, model: str) -> str:
        return f"{self.base_url}/models/{model}:generateContent"

    @staticmethod
    def _generation_config(kwargs: dict[str, Any]) -> dict[str, Any]:
        config = dict(kwargs)
        if "max_tokens" in config:
            config["maxOutputTokens"] = config.pop("max_tokens")
        if "top_p" in config:
            config["topP"] = config.pop("top_p")
        if "top_k" in config:
            config["topK"] = config.pop("top_k")
        return config

    @staticmethod
    def _contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contents = []
        for message in messages:
            role = message.get("role")
            # Gemini's content roles are user/model. System instructions are
            # represented separately when possible, so don't send them as model turns.
            if role == "system":
                continue
            contents.append({
                "role": "user" if role == "user" else "model",
                "parts": [{"text": str(message.get("content", ""))}],
            })
        return contents

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/models", params={"key": self.api_key})
            response.raise_for_status()
            payload = response.json()
        result = []
        for item in payload.get("models", []):
            model_id = item.get("name", "").removeprefix("models/")
            if model_id:
                methods = item.get("supportedGenerationMethods") or []
                if methods and "generateContent" not in methods:
                    continue
                result.append({
                    "id": model_id,
                    "display_name": item.get("displayName") or model_id,
                    "context_window": item.get("inputTokenLimit"),
                    "max_output_tokens": item.get("outputTokenLimit"),
                    "supports_streaming": "streamGenerateContent" in methods if methods else True,
                    "raw_metadata": item,
                })
        return result

    async def chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        body = {"contents": self._contents(messages)}
        config = self._generation_config(kwargs)
        if config:
            body["generationConfig"] = config
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._url(model), params={"key": self.api_key}, json=body)
            response.raise_for_status()
            return response.json()

    async def stream_chat_completion(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[str]:
        body = {"contents": self._contents(messages)}
        config = self._generation_config(kwargs)
        if config:
            body["generationConfig"] = config
        url = f"{self.base_url}/models/{model}:streamGenerateContent"
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, params={"key": self.api_key, "alt": "sse"}, json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        yield line[5:].strip()
