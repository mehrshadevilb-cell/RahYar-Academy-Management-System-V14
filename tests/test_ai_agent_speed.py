from src.services.ai_agent_speed import (
    ordered_skills_for_task,
    skill_budget_chars,
    wants_debug_skill,
)


def test_fix_tasks_request_debug_skill():
    assert wants_debug_skill("handler returns 500", "fix") is True
    assert wants_debug_skill("اضافه کردن دکمه جدید", "feature") is False
    assert wants_debug_skill("traceback in payment approve", "feature") is True


def test_skill_budget_is_tighter_for_fixes():
    assert skill_budget_chars("fix", "crash") < skill_budget_chars("feature", "new button")


def test_debug_skill_ordered_first_when_relevant():
    available = ["telegram_ui.md", "security.md", "coding.md", "review.md", "debug.md"]
    ordered = ordered_skills_for_task("fix reservation crash", "fix", available)
    assert ordered[0] == "security.md"
    assert "debug.md" in ordered
    assert ordered.index("debug.md") < ordered.index("telegram_ui.md")
