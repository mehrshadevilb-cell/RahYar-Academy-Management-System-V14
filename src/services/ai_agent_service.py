"""Safe, bounded AI developer agent for owner-controlled maintenance.

The agent is deliberately disabled by default. It operates on a local checkout,
creates an ai/* branch, and never changes main automatically.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from src.core.config.settings import get_settings


class AIAgentError(RuntimeError):
    pass


class AIAgentService:
    PROTECTED = {".env", ".git", ".github/workflows/secrets.yml"}
    MAX_FILE_BYTES = 120_000

    def __init__(self) -> None:
        self.settings = get_settings()
        self.repo = Path(self.settings.AI_AGENT_REPO_PATH).resolve()

    def _check_enabled(self) -> None:
        if not self.settings.AI_AGENT_ENABLED:
            raise AIAgentError("AI Developer Agent is disabled in configuration.")
        if not self.settings.AI_AGENT_API_KEY:
            raise AIAgentError("AI_AGENT_API_KEY is not configured.")
        if not self.repo.exists() or not (self.repo / ".git").exists():
            raise AIAgentError(f"AI_AGENT_REPO_PATH is not a git checkout: {self.repo}")

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, text=True, capture_output=True, timeout=60
        )
        if result.returncode:
            raise AIAgentError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def status(self) -> str:
        self._check_enabled()
        branch = self._git("branch", "--show-current")
        clean = not bool(self._git("status", "--porcelain"))
        return f"branch={branch}; clean={clean}"

    def _context(self) -> str:
        context_file = self.repo / "AI_PROJECT_CONTEXT.md"
        context = context_file.read_text(encoding="utf-8") if context_file.exists() else ""
        tracked = self._git("ls-files")
        return f"PROJECT CONTEXT:\n{context}\n\nTRACKED FILES:\n{tracked}"

    def _request_model(self, prompt: str) -> str:
        url = self.settings.AI_AGENT_BASE_URL.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.AI_AGENT_MODEL,
            "messages": [
                {"role": "system", "content": "You are the RahYar senior software engineer. Follow AI_PROJECT_CONTEXT.md exactly. Never suggest secrets. Return concise, actionable engineering output."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.AI_AGENT_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.AI_AGENT_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIAgentError(f"AI provider request failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIAgentError("AI provider returned an unexpected response.") from exc

    def analyze(self, request: str = "Audit the repository for bugs, risks, missing tests and architecture issues.") -> str:
        self._check_enabled()
        status = self._git("status", "--short")
        prompt = f"""{self._context()}\n\nCURRENT GIT STATUS:\n{status}\n\nTASK:\n{request}\n\nDo not modify files. Return findings grouped by severity, with exact paths and concrete remediation steps."""
        return self._request_model(prompt)

    def _ensure_branch(self, purpose: str) -> str:
        current = self._git("branch", "--show-current")
        if current.startswith("ai/"):
            return current
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in purpose).strip("-")[:45]
        branch = f"ai/{slug or 'maintenance'}"
        self._git("switch", "-c", branch)
        return branch

    def _safe_path(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.parts[0] in self.PROTECTED:
            raise AIAgentError(f"Protected or invalid path: {relative}")
        target = (self.repo / path).resolve()
        if self.repo not in target.parents and target != self.repo:
            raise AIAgentError(f"Path escapes repository: {relative}")
        return target

    def implement(self, task: str) -> str:
        self._check_enabled()
        branch = self._ensure_branch(task)
        prompt = f"""{self._context()}\n\nTASK:\n{task}\n\nReturn ONLY valid JSON with this exact shape: {{\"summary\": string, \"files\": [{{\"path\": string, \"content\": string}}]}}. Include complete file contents, not diffs. Change only the minimum required files. Never include .env, secrets, credentials, or production data."""
        raw = self._request_model(prompt).strip()
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1]
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIAgentError("AI did not return valid JSON changes.") from exc
        files = plan.get("files", [])
        if not isinstance(files, list) or not files:
            raise AIAgentError("AI returned no file changes.")
        for item in files:
            path = self._safe_path(str(item.get("path", "")))
            content = str(item.get("content", ""))
            if len(content.encode("utf-8")) > self.MAX_FILE_BYTES:
                raise AIAgentError(f"Refusing oversized AI file change: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        compile_result = subprocess.run(
            ["python", "-m", "compileall", "-q", "src", "tests"],
            cwd=self.repo, text=True, capture_output=True, timeout=180,
        )
        if compile_result.returncode:
            return f"Branch: {branch}\nCompile failed; changes were NOT committed.\n{compile_result.stderr}"

        test_result = subprocess.run(
            ["python", "-m", "pytest", "-q"],
            cwd=self.repo, text=True, capture_output=True, timeout=600,
        )
        if test_result.returncode:
            return f"Branch: {branch}\nTests failed; changes were NOT committed.\n{test_result.stdout[-5000:]}\n{test_result.stderr[-3000:]}"

        self._git("add", "--", *[str(item["path"]) for item in files])
        self._git("commit", "-m", f"ai: {task[:60]}")
        return f"Branch: {branch}\nTests: PASS\nCommitted: {self._git('rev-parse', '--short', 'HEAD')}\nSummary: {plan.get('summary', 'completed')}"
