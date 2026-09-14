from src.ai.client import AIDeveloperClient


class AIDeveloperService:
    def __init__(self) -> None:
        self.client = AIDeveloperClient()

    async def analyze(self, request: str) -> dict:
        return await self.client.chat(
            request,
            system=(
                "You are RahYar AI Developer Agent. "
                "Analyze the codebase, suggest safe changes, and never expose secrets."
            ),
        )
