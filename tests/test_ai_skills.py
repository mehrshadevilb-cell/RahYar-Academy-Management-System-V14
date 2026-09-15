from src.services.ai_skills.registry import SkillRegistry
from src.services.ai_skills.web_search import web_search


def test_builtin_skills_present():
    registry = SkillRegistry(repo_root=None)
    ids = {s.id for s in registry.list_skills()}
    assert {"coding", "ui_polish", "web_research", "debug"} <= ids


def test_resolve_modes():
    registry = SkillRegistry(repo_root=None)
    ui = registry.resolve_for_mode("ui")
    assert any(s.id == "ui_polish" for s in ui)
    research = registry.resolve_for_mode("research")
    assert any(s.id == "web_research" for s in research)
    tools = registry.allowed_tools(research)
    assert "web_search" in tools


def test_web_search_empty_query():
    assert "empty" in web_search("").lower()
