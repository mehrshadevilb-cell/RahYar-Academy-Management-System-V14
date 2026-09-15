from pathlib import Path

from src.services.ai_agent_diagnostics import AIAgentDiagnostics


def _minimal_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "alembic" / "versions").mkdir(parents=True)
    (tmp_path / "src" / "ok.py").write_text("value = 1\n", encoding="utf-8")
    return tmp_path


def test_quick_diagnostics_accepts_clean_repo(tmp_path: Path):
    repo = _minimal_repo(tmp_path)
    results = AIAgentDiagnostics(repo).quick()
    assert all(item.ok for item in results)


def test_duplicate_migration_revision_is_reported(tmp_path: Path):
    repo = _minimal_repo(tmp_path)
    for name in ("001_a.py", "002_b.py"):
        (repo / "alembic" / "versions" / name).write_text(
            "revision = 'same'\ndown_revision = None\n",
            encoding="utf-8",
        )
    result = AIAgentDiagnostics(repo).migration_graph()
    assert not result.ok
    assert "same" in result.detail


def test_main_branch_is_rejected_for_agent_writes(tmp_path: Path, monkeypatch):
    repo = _minimal_repo(tmp_path)
    checker = AIAgentDiagnostics(repo)
    monkeypatch.setattr(checker, "_run", lambda args, timeout: (True, "main") if args[-1] == "--show-current" else (True, ""))
    result = checker.git_hygiene()
    assert not result.ok
    assert "main" in result.detail


def test_secret_like_literal_is_flagged(tmp_path: Path):
    repo = _minimal_repo(tmp_path)
    (repo / "src" / "bad.py").write_text(
        "api_key = 'this-is-a-long-hard-coded-secret'\n",
        encoding="utf-8",
    )
    result = AIAgentDiagnostics(repo).secret_literals()
    assert not result.ok
    assert "bad.py" in result.detail
