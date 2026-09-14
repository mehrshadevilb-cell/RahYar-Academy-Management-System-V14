from pathlib import Path

import pytest

from src.services.ai_agent_service import AIAgentError, AIAgentService


def test_safe_path_rejects_empty_and_parent_paths(tmp_path, monkeypatch):
    agent = AIAgentService()
    agent.repo = Path(tmp_path)
    with pytest.raises(AIAgentError):
        agent._safe_path("")
    with pytest.raises(AIAgentError):
        agent._safe_path("../secret.txt")
    with pytest.raises(AIAgentError):
        agent._safe_path(".env")


def test_safe_path_allows_project_file(tmp_path):
    agent = AIAgentService()
    agent.repo = Path(tmp_path)
    assert agent._safe_path("src/example.py") == Path(tmp_path).resolve() / "src/example.py"
