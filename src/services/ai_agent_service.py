"""Safe, bounded AI developer agent for owner-controlled maintenance.

The agent is deliberately disabled by default. It operates on a local checkout,
creates an ai/* branch, and never changes main automatically.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.core.config.settings import get_settings


class AIAgentError(RuntimeError):
    pass


class AIAgentService:
    PROTECTED = {".env", ".git", ".github/workflows/secrets.yml"}
    MAX_FILE_BYTES = 120_000
    LOCK_NAME = ".ai-agent/run.lock"
    LOCK_STALE_SECONDS = 30 * 60

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
            ["git", *args],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise AIAgentError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def _lock_path(self) -> Path:
        return self.repo / self.LOCK_NAME

    def _acquire_lock(self) -> None:
        path = self._lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                age = time.time() - path.stat().st_mtime
            except OSError:
                age = 0
            if age < self.LOCK_STALE_SECONDS:
                raise AIAgentError(
                    "Agent is already running. Wait for the current task to finish "
                    "or clear a stale lock after 30 minutes."
                )
            path.unlink(missing_ok=True)
        path.write_text(f"pid={os.getpid()}\nstarted={time.time()}\n", encoding="utf-8")

    def _release_lock(self) -> None:
        try:
            self._lock_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _reset_worktree(self) -> None:
        """Discard uncommitted AI edits after a failed compile/test cycle."""
        subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=60,
        )
        subprocess.run(
            ["git", "clean", "-fd", "-e", self.LOCK_NAME],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=60,
        )

    def status(self) -> str:
        self._check_enabled()
        branch = self._git("branch", "--show-current")
        dirty = self._git("status", "--porcelain")
        clean = not bool(dirty)
        head = self._git("rev-parse", "--short", "HEAD")
        lock = self._lock_path().exists()
        lines = [
            f"enabled={self.settings.AI_AGENT_ENABLED}",
            f"branch={branch}",
            f"head={head}",
            f"clean={clean}",
            f"locked={lock}",
            f"model={self.settings.AI_AGENT_MODEL}",
            f"max_retries={self.settings.AI_AGENT_MAX_RETRIES}",
            f"repo={self.repo}",
        ]
        if dirty:
            lines.append(f"dirty_files={len(dirty.splitlines())}")
        return "\n".join(lines)

    def _context(self) -> str:
        context_file = self.repo / "AI_PROJECT_CONTEXT.md"
        context = context_file.read_text(encoding="utf-8") if context_file.exists() else ""
        policy_file = self.repo / ".ai-agent" / "policy.md"
        policy = policy_file.read_text(encoding="utf-8") if policy_file.exists() else ""
        tracked = self._git("ls-files")
        return (
            f"PROJECT CONTEXT:\n{context}\n\n"
            f"AGENT POLICY:\n{policy}\n\n"
            f"TRACKED FILES:\n{tracked}"
        )

    def _request_model(self, prompt: str) -> str:
        url = self.settings.AI_AGENT_BASE_URL.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.AI_AGENT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the RahYar senior software engineer. "
                        "Follow AI_PROJECT_CONTEXT.md and .ai-agent/policy.md exactly. "
                        "Never suggest secrets. Return concise, actionable engineering output."
                    ),
                },
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
            with urllib.request.urlopen(
                request, timeout=self.settings.AI_AGENT_TIMEOUT_SECONDS
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIAgentError(f"AI provider request failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIAgentError("AI provider returned an unexpected response.") from exc

    def analyze(
        self,
        request: str = (
            "Audit the repository for bugs, risks, missing tests and architecture issues."
        ),
    ) -> str:
        self._check_enabled()
        self._acquire_lock()
        try:
            status = self._git("status", "--short")
            prompt = f"""{self._context()}

CURRENT GIT STATUS:
{status}

TASK:
{request}

Do not modify files. Return findings grouped by severity, with exact paths and concrete remediation steps."""
            return self._request_model(prompt)
        finally:
            self._release_lock()

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
        if not path.parts or path.is_absolute() or ".." in path.parts or path.parts[0] in self.PROTECTED:
            raise AIAgentError(f"Protected or invalid path: {relative}")
        # Extra deny patterns from policy
        lowered = str(path).lower()
        for token in (".env", "secrets", "credentials", "production.db"):
            if token in lowered:
                raise AIAgentError(f"Protected or invalid path: {relative}")
        target = (self.repo / path).resolve()
        if self.repo not in target.parents and target != self.repo:
            raise AIAgentError(f"Path escapes repository: {relative}")
        return target

    def _parse_plan(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = text.removeprefix("```").removeprefix("json").removesuffix("```").strip()
        try:
            plan = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIAgentError("AI did not return valid JSON changes.") from exc
        files = plan.get("files", [])
        if not isinstance(files, list) or not files:
            raise AIAgentError("AI returned no file changes.")
        return plan

    def _apply_files(self, files: list) -> list[str]:
        written: list[str] = []
        for item in files:
            rel = str(item.get("path", ""))
            path = self._safe_path(rel)
            content = str(item.get("content", ""))
            if len(content.encode("utf-8")) > self.MAX_FILE_BYTES:
                raise AIAgentError(f"Refusing oversized AI file change: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written.append(rel)
        return written

    def _run_checks(self) -> tuple[bool, str]:
        compile_result = subprocess.run(
            ["python", "-m", "compileall", "-q", "src", "tests"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=180,
        )
        if compile_result.returncode:
            return False, f"Compile failed.\n{compile_result.stderr or compile_result.stdout}"

        test_result = subprocess.run(
            ["python", "-m", "pytest", "-q"],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=600,
        )
        if test_result.returncode:
            out = (test_result.stdout or "")[-5000:]
            err = (test_result.stderr or "")[-3000:]
            return False, f"Tests failed.\n{out}\n{err}"
        return True, "PASS"

    def implement(self, task: str, task_type: str = "feature") -> str:
        self._check_enabled()
        self._acquire_lock()
        try:
            branch = self._ensure_branch(task)
            task_type = (task_type or "feature").strip().lower()
            if task_type not in {"fix", "feature"}:
                task_type = "feature"

            intent = (
                "Fix the described bug with the smallest safe change. Preserve existing behavior elsewhere."
                if task_type == "fix"
                else "Implement the described feature with the smallest clean change that fits the architecture."
            )

            max_retries = max(0, int(self.settings.AI_AGENT_MAX_RETRIES))
            last_error = ""

            for attempt in range(max_retries + 1):
                feedback = ""
                if last_error:
                    feedback = (
                        f"\n\nPREVIOUS ATTEMPT FAILED (attempt {attempt}/{max_retries}):\n"
                        f"{last_error}\n"
                        "Produce a corrected JSON plan that fixes the failure."
                    )

                prompt = f"""{self._context()}

TASK TYPE: {task_type}
INTENT: {intent}

TASK:
{task}
{feedback}

Return ONLY valid JSON with this exact shape:
{{"summary": string, "files": [{{"path": string, "content": string}}]}}

Include complete file contents, not diffs.
Change only the minimum required files.
Never include .env, secrets, credentials, or production data.
Never push to main."""

                try:
                    raw = self._request_model(prompt)
                    plan = self._parse_plan(raw)
                    written = self._apply_files(plan.get("files", []))
                except AIAgentError as exc:
                    last_error = str(exc)
                    self._reset_worktree()
                    if attempt >= max_retries:
                        return (
                            f"Branch: {branch}\n"
                            f"Attempts: {attempt + 1}\n"
                            f"Failed after retries.\n{last_error}"
                        )
                    continue

                ok, check_msg = self._run_checks()
                if not ok:
                    last_error = check_msg
                    self._reset_worktree()
                    if attempt >= max_retries:
                        return (
                            f"Branch: {branch}\n"
                            f"Attempts: {attempt + 1}\n"
                            f"Checks failed; changes were NOT committed.\n{check_msg}"
                        )
                    continue

                self._git("add", "--", *written)
                self._git("commit", "-m", f"ai({task_type}): {task[:60]}")
                return (
                    f"Branch: {branch}\n"
                    f"Attempts: {attempt + 1}\n"
                    f"Tests: PASS\n"
                    f"Committed: {self._git('rev-parse', '--short', 'HEAD')}\n"
                    f"Files: {', '.join(written)}\n"
                    f"Summary: {plan.get('summary', 'completed')}"
                )

            return f"Branch: {branch}\nFailed after retries.\n{last_error}"
        finally:
            self._release_lock()
