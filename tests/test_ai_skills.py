from pathlib import Path

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


def test_ui_mode_loads_design_file_skills(tmp_path: Path):
    skills_dir = tmp_path / ".ai-agent" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "sample_design.md").write_text(
        "title: نمونه طراحی\n"
        "description: تست\n"
        "tools: read_file\n"
        "tags: design, ux\n"
        "\n"
        "Design rules here.\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(repo_root=tmp_path)
    ui_skills = registry.resolve_for_mode("ui")
    ids = {s.id for s in ui_skills}
    assert "ui_polish" in ids
    assert "sample_design" in ids


def test_web_search_empty_query():
    assert "empty" in web_search("").lower()
