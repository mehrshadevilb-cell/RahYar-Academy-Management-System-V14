from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class BaseAIProvider(ABC):
    def __init__(self, base_url: str, api_key: str, extra_config: dict[str, Any] | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.extra_config = extra_config or {}

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def chat_completion(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat_completion(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        raise NotImplementedError
