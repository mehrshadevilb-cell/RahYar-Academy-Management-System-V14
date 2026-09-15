"""Deterministic diagnostics for the RahYar AI developer agent."""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Diagnostic:
    name: str
    ok: bool
    detail: str
    duration_ms: int = 0


class AIAgentDiagnostics:
    """Bounded repository diagnostics suitable for owner-facing bot tools."""

    SCANNED_SUFFIXES = {".py", ".yml", ".yaml", ".toml", ".ini", ".md"}
    SECRET_PATTERNS = (
        re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*=\s*['\"][^'\"]{12,}['\"]"),
        re.compile(r"(?i)\b(ghp|github_pat|sk-[a-z0-9_-]{12,})[a-z0-9_-]+"),
    )
    PROTECTED_NAMES = {".env", ".env.local", ".env.production", "credentials.json", "secrets.json"}

    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo).resolve()

    def _run(self, args: list[str], timeout: int) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                args,
                cwd=self.repo,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"{type(exc).__name__}: {exc}"
        output = (result.stdout or result.stderr or "").strip()
        return result.returncode == 0, output[-5000:]

    def _files(self) -> Iterable[Path]:
        for root_name in ("src", "tests", "alembic", "docs"):
            root = self.repo / root_name
            if not root.is_dir():
                continue
            yield from (p for p in root.rglob("*") if p.is_file() and p.suffix in self.SCANNED_SUFFIXES)

    def syntax(self) -> Diagnostic:
        count = 0
        for path in self._files():
            if path.suffix != ".py":
                continue
            count += 1
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                return Diagnostic("syntax", False, f"{path.relative_to(self.repo)}: {exc}")
        return Diagnostic("syntax", True, f"AST parse passed ({count} Python files)")

    def migration_graph(self) -> Diagnostic:
        root = self.repo / "alembic" / "versions"
        if not root.is_dir():
            return Diagnostic("migrations", True, "no Alembic versions directory")
        revisions: dict[str, str] = {}
        duplicates: list[str] = []
        for path in sorted(root.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError):
                continue
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if not any(isinstance(t, ast.Name) and t.id == "revision" for t in node.targets):
                    continue
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, str):
                    if value in revisions:
                        duplicates.append(f"{value}: {revisions[value]} / {path.name}")
                    revisions[value] = path.name
        if duplicates:
            return Diagnostic("migrations", False, "duplicate revisions: " + " | ".join(duplicates[:8]))
        return Diagnostic("migrations", True, f"unique revisions ({len(revisions)})")

    def git_hygiene(self) -> Diagnostic:
        if not (self.repo / ".git").is_dir():
            # Temporary/minimal repos used by unit tests and diagnostics probes
            # are intentionally allowed to omit a real Git worktree.
            return Diagnostic("git", True, "git metadata not present; hygiene check skipped for probe repo")
        ok, output = self._run(["git", "diff", "--check"], 30)
        if not ok:
            return Diagnostic("git", False, output or "git diff --check failed")
        ok, branch = self._run(["git", "branch", "--show-current"], 15)
        if not ok:
            return Diagnostic("git", False, branch or "cannot determine branch")
        branch = branch.strip()
        if branch == "main":
            return Diagnostic("git", False, "agent write operations must not target main")
        return Diagnostic("git", True, f"branch={branch or '(detached)'}; diff-check passed")

    def protected_files(self) -> Diagnostic:
        violations: list[str] = []
        for path in self._files():
            rel = path.relative_to(self.repo)
            if path.name in self.PROTECTED_NAMES or ".env." in path.name:
                violations.append(str(rel))
        if violations:
            return Diagnostic("protected-files", False, "secret-like files visible in source tree: " + ", ".join(violations[:8]))
        return Diagnostic("protected-files", True, "no protected environment/credential files in scanned roots")

    def secret_literals(self) -> Diagnostic:
        findings: list[str] = []
        for path in self._files():
            if path.name in self.PROTECTED_NAMES or ".env" in path.name:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern in self.SECRET_PATTERNS:
                if pattern.search(text):
                    findings.append(str(path.relative_to(self.repo)))
                    break
            if len(findings) >= 8:
                break
        if findings:
            return Diagnostic("secret-scan", False, "possible hard-coded secret pattern in: " + ", ".join(findings))
        return Diagnostic("secret-scan", True, "no obvious hard-coded secret patterns detected")

    def quick(self) -> list[Diagnostic]:
        """Fast checks intended for every agent task."""
        return [self.syntax(), self.migration_graph(), self.git_hygiene(), self.protected_files(), self.secret_literals()]

    def full(self) -> list[Diagnostic]:
        """Quick checks plus compile and the complete pytest suite."""
        results = self.quick()
        ok, output = self._run([sys.executable, "-m", "compileall", "-q", "-f", "src", "tests"], 180)
        results.append(Diagnostic("compile", ok, "compileall passed" if ok else output))
        if ok:
            ok, output = self._run([sys.executable, "-m", "pytest", "-q"], 600)
            results.append(Diagnostic("pytest", ok, "pytest passed" if ok else output))
        else:
            results.append(Diagnostic("pytest", False, "skipped because compile failed"))
        return results

    @staticmethod
    def summary(results: list[Diagnostic]) -> str:
        passed = sum(item.ok for item in results)
        failed = len(results) - passed
        lines = [f"AI diagnostics: {passed}/{len(results)} passed; {failed} failed"]
        for item in results:
            lines.append(f"{'PASS' if item.ok else 'FAIL'} {item.name}: {item.detail}")
        return "\n".join(lines)
