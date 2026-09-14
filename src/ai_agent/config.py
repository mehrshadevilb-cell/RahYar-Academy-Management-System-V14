from dataclasses import dataclass


@dataclass
class AgentConfig:
    enabled: bool = False
    provider: str = "agentrouter"
    model: str | None = None
    auto_commit: bool = False
    auto_deploy: bool = False
