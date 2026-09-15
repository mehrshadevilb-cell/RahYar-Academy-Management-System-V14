from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.ai_agent_service import AIAgentError, AIAgentService
from src.bot.handlers.admin_ai import _safe_html


def test_safe_path_rejects_empty_and_parent_paths(tmp_path):
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


def test_safe_path_rejects_absolute(tmp_path):
    agent = AIAgentService()
    agent.repo = Path(tmp_path)
    with pytest.raises(AIAgentError):
        agent._safe_path("/etc/passwd")


def test_safe_path_rejects_secrets_token(tmp_path):
    agent = AIAgentService()
    agent.repo = Path(tmp_path)
    with pytest.raises(AIAgentError):
        agent._safe_path("config/secrets.yaml")


def test_parse_plan_accepts_fenced_json():
    agent = AIAgentService()
    raw = '```json\n{"summary": "ok", "files": [{"path": "a.py", "content": "x"}]}\n```'
    plan = agent._parse_plan(raw)
    assert plan["summary"] == "ok"
    assert plan["files"][0]["path"] == "a.py"


def test_parse_plan_rejects_empty_files():
    agent = AIAgentService()
    with pytest.raises(AIAgentError):
        agent._parse_plan('{"summary": "x", "files": []}')


def test_apply_files_writes_under_repo(tmp_path):
    agent = AIAgentService()
    agent.repo = Path(tmp_path)
    written = agent._apply_files([{"path": "src/demo.py", "content": "print(1)\n"}])
    assert written == ["src/demo.py"]
    assert (tmp_path / "src" / "demo.py").read_text(encoding="utf-8") == "print(1)\n"


def test_apply_files_rejects_oversized(tmp_path):
    agent = AIAgentService()
    agent.repo = Path(tmp_path)
    big = "x" * (AIAgentService.MAX_FILE_BYTES + 10)
    with pytest.raises(AIAgentError):
        agent._apply_files([{"path": "big.py", "content": big}])


def test_implement_disabled_raises():
    agent = AIAgentService()
    agent.settings = MagicMock()
    agent.settings.AI_AGENT_ENABLED = False
    with pytest.raises(AIAgentError, match="AI_AGENT_ENABLED|خاموش"):
        agent.implement("do something")


def test_lock_blocks_second_acquire(tmp_path):
    agent = AIAgentService()
    agent.repo = Path(tmp_path)
    agent._acquire_lock()
    with pytest.raises(AIAgentError, match="Task|صبر"):
        agent._acquire_lock()
    agent._release_lock()
    agent._acquire_lock()
    agent._release_lock()


def test_ai_audit_output_is_safe_for_telegram_html():
    assert _safe_html("<script>alert('x')</script> & details") == "&lt;script&gt;alert('x')&lt;/script&gt; &amp; details"
