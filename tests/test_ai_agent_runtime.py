import json

from src.services.ai_agent_runtime import AIAgentRuntime


def test_skill_selection_always_includes_security_coding_review(tmp_path):
    class DummyAgent:
        repo = tmp_path

    skills = tmp_path / ".ai-agent" / "skills"
    skills.mkdir(parents=True)
    for name in ("security.md", "coding.md", "review.md", "telegram_ui.md", "debug.md"):
        (skills / name).write_text(f"# {name}", encoding="utf-8")

    runtime = AIAgentRuntime(DummyAgent())
    selected = runtime.select_skills("add a Telegram keyboard feature", "feature")

    assert "security.md" in selected
    assert "coding.md" in selected
    assert "review.md" in selected
    assert "telegram_ui.md" in selected


def test_fix_task_selects_debug_skill(tmp_path):
    class DummyAgent:
        repo = tmp_path

    skills = tmp_path / ".ai-agent" / "skills"
    skills.mkdir(parents=True)
    for name in ("security.md", "coding.md", "review.md", "debug.md"):
        (skills / name).write_text(f"# {name}", encoding="utf-8")

    runtime = AIAgentRuntime(DummyAgent())
    selected = runtime.select_skills("payment handler raises AttributeError", "fix")
    assert "debug.md" in selected


def test_parse_plan_accepts_json_fence():
    plan = AIAgentRuntime._parse_plan(
        "```json\n" + json.dumps({
            "objective": "fix callback flow",
            "approach": ["inspect handler", "add test"],
            "skills": ["security.md"],
            "inspect": ["src/bot/handlers"],
            "risks": ["regression"],
            "tests": ["pytest -q"],
        }) + "\n```"
    )
    assert plan.objective == "fix callback flow"
    assert plan.tests == ["pytest -q"]
