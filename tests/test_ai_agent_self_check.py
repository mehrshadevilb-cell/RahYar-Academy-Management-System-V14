from pathlib import Path

from src.services.ai_agent_self_check import AIAgentSelfChecker


def test_self_checker_reports_missing_required_files(tmp_path: Path):
    checker = AIAgentSelfChecker(tmp_path)
    results = checker.run()
    layout = next(item for item in results if item.name == "layout")
    assert layout.ok is False
    assert "pyproject.toml" in layout.detail


def test_self_checker_accepts_valid_minimal_layout(tmp_path: Path):
    required = (
        "pyproject.toml",
        "requirements.txt",
        "alembic.ini",
        "src/main.py",
        "src/bot/bot.py",
        "src/database/session.py",
    )
    for relative in required:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# placeholder\n", encoding="utf-8")

    (tmp_path / "src/main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src/bot/bot.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src/database/session.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    checker = AIAgentSelfChecker(tmp_path)
    results = checker.run()
    assert next(item for item in results if item.name == "layout").ok
    assert next(item for item in results if item.name == "syntax").ok
