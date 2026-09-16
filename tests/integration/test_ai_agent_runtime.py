import pytest

from src.services.ai_agent_self_check import AIAgentSelfChecker
from src.services.ai_agent_runtime import AIAgentRuntime


class FakeAgent:
    def __init__(self):
        self.repo = __import__("pathlib").Path(".")
        self.calls = []

    def _request_model(self, prompt):
        return '{"objective":"test","approach":[],"skills":[],"inspect":[],"risks":[],"tests":[]}'

    def implement(self, task, task_type):
        self.calls.append((task, task_type))
        return "Branch: ai/test\nTests: PASS"


@pytest.mark.asyncio
async def test_runtime_write_records_audit_and_completes(monkeypatch):
    runtime = AIAgentRuntime(FakeAgent())
    runtime._redis = None
    monkeypatch.setattr(AIAgentSelfChecker, "run", lambda self: [])
    events = []
    monkeypatch.setattr(runtime, "_audit", lambda user_id, action, description: events.append(action))

    result = await runtime.run_write(777, "add a regression test", "tests")

    assert "Tests: PASS" in result
    assert events == ["AI_AGENT_START", "AI_AGENT_SUCCESS"]


@pytest.mark.asyncio
async def test_runtime_records_failure(monkeypatch):
    agent = FakeAgent()
    agent.implement = lambda task, task_type: (_ for _ in ()).throw(RuntimeError("boom"))
    runtime = AIAgentRuntime(agent)
    runtime._redis = None
    monkeypatch.setattr(AIAgentSelfChecker, "run", lambda self: [])
    events = []
    monkeypatch.setattr(runtime, "_audit", lambda user_id, action, description: events.append(action))

    with pytest.raises(RuntimeError, match="boom"):
        await runtime.run_write(777, "break something", "fix")

    assert events == ["AI_AGENT_START", "AI_AGENT_FAILURE"]
