"""Fast, deterministic runtime checks for the RahYar AI Developer Agent.

These checks intentionally do not call an LLM. They catch cheap, objective
failures before an AI task is started and after code has been changed.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


class AIAgentSelfChecker:
    """Read-only project preflight suitable for production diagnostics."""

    SOURCE_ROOTS = ("src", "tests")
    REQUIRED_FILES = (
        "pyproject.toml",
        "requirements.txt",
        "alembic.ini",
        "src/main.py",
        "src/bot/bot.py",
        "src/database/session.py",
    )

    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo).resolve()

    def _python_files(self) -> list[Path]:
        files: list[Path] = []
        for root_name in self.SOURCE_ROOTS:
            root = self.repo / root_name
            if root.is_dir():
                files.extend(sorted(root.rglob("*.py")))
        return files

    def _check_layout(self) -> CheckResult:
        missing = [p for p in self.REQUIRED_FILES if not (self.repo / p).is_file()]
        if missing:
            return CheckResult("layout", False, "missing: " + ", ".join(missing[:8]))
        return CheckResult("layout", True, f"required files present ({len(self.REQUIRED_FILES)})")

    def _check_python_syntax(self) -> CheckResult:
        files = self._python_files()
        errors: list[str] = []
        for path in files:
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                errors.append(f"{path.relative_to(self.repo)}: {type(exc).__name__}: {exc}")
                if len(errors) >= 8:
                    break
        if errors:
            return CheckResult("syntax", False, " | ".join(errors))
        return CheckResult("syntax", True, f"AST parse passed ({len(files)} Python files)")

    def _check_migration_ids(self) -> CheckResult:
        root = self.repo / "alembic" / "versions"
        if not root.is_dir():
            return CheckResult("migrations", False, "alembic/versions is missing")
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for path in sorted(root.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError):
                continue
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "revision":
                        try:
                            value = ast.literal_eval(node.value)
                        except (ValueError, TypeError):
                            continue
                        if isinstance(value, str):
                            previous = seen.get(value)
                            if previous:
                                duplicates.append(f"{value}: {previous}, {path.name}")
                            else:
                                seen[value] = path.name
        if duplicates:
            return CheckResult("migrations", False, "duplicate revision ids: " + " | ".join(duplicates[:6]))
        return CheckResult("migrations", True, f"unique revision ids ({len(seen)})")

    def _check_imports(self) -> CheckResult:
        # Probe modules independently and in parallel so one slow import is
        # isolated and diagnostics finish faster.
        modules = (
            "src.main",
            "src.bot.bot",
            "src.services.ai_agent_runtime",
            "src.services.routed_ai_agent_service",
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo)
        env["RAHYAR_SELF_CHECK"] = "1"

        def probe(module: str) -> tuple[str, str]:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", f"import {module}"],
                    cwd=self.repo,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=12,
                )
            except subprocess.TimeoutExpired:
                return module, "timeout>12s"
            except OSError as exc:
                return module, f"{type(exc).__name__}: {exc}"
            if result.returncode:
                detail = (result.stderr or result.stdout).strip().replace("\n", " ")
                return module, detail[:300]
            return module, "ok"

        from concurrent.futures import ThreadPoolExecutor, as_completed
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=len(modules), thread_name_prefix="ra-import") as pool:
            futures = [pool.submit(probe, module) for module in modules]
            for future in as_completed(futures):
                module, status = future.result()
                if status != "ok":
                    failures.append(f"{module}: {status}")
        if failures:
            return CheckResult("imports", False, " | ".join(sorted(failures)))
        return CheckResult("imports", True, f"critical modules import successfully ({len(modules)} parallel probes)")

    def _check_git(self) -> CheckResult:
        if not (self.repo / ".git").exists():
            return CheckResult("git", True, "skipped: .git metadata is not mounted in this runtime image")
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=self.repo,
                text=True,
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CheckResult("git", False, f"{type(exc).__name__}: {exc}")
        if result.returncode:
            return CheckResult("git", False, (result.stderr or "git status failed")[:700])
        changed = len([line for line in result.stdout.splitlines() if line.strip()])
        return CheckResult("git", True, f"repository reachable; working-tree entries={changed}")

    def run(self) -> list[CheckResult]:
        """Run only bounded local checks; never mutate the repository."""
        return [
            self._check_layout(),
            self._check_python_syntax(),
            self._check_migration_ids(),
            self._check_imports(),
            self._check_git(),
        ]

    def format(self) -> str:
        results = self.run()
        passed = sum(item.ok for item in results)
        lines = ["🤖 <b>RahYar Agent Self-Check</b>", "━━━━━━━━━━━━━━━━━━"]
        for item in results:
            icon = "🟢" if item.ok else "🔴"
            lines.append(f"{icon} <b>{item.name}</b> · {item.detail}")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append(f"Result: <b>{passed}/{len(results)} checks passed</b>")
        return "\n".join(lines)

    def assert_healthy(self) -> None:
        failures = [item for item in self.run() if not item.ok]
        if failures:
            detail = " | ".join(f"{x.name}: {x.detail}" for x in failures)
            raise RuntimeError(f"Agent self-check failed: {detail}")
