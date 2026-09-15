"""Safe, bounded AI developer agent for owner-controlled maintenance.

Creates ai/* branches only. Never merges to main automatically.

Write modes:
- Local: AI_AGENT_REPO_PATH points at a git checkout
- Online (Render): AI_AGENT_WRITE_ENABLED + GITHUB_TOKEN + GITHUB_REPO
  clones into AI_AGENT_WORK_DIR, commits, pushes, opens a PR

Skills exposed to the owner (via src/bot/handlers/admin_ai.py):
- status / analyze (debug, assistant consult)   - read-only
- list_ai_branches / read_file / search_code    - read-only
- implement(task, task_type)                    - fix | feature | refactor | tests
  writes only to ai/* branches, runs tests before committing, opens a PR
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse

from src.core.config.settings import get_settings


class AIAgentError(RuntimeError):
    pass


class AIAgentService:
    PROTECTED = {".env", ".git", ".github/workflows/secrets.yml"}
    MAX_FILE_BYTES = 120_000
    MAX_READ_CHARS = 4000
    SEARCHABLE_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".txt", ".html"}
    LOCK_NAME = ".ai-agent/run.lock"
    LOCK_STALE_SECONDS = 30 * 60

    TASK_INTENTS = {
        "fix": "Fix the described bug with the smallest safe change.",
        "feature": "Implement the feature with the smallest clean change.",
        "refactor": (
            "Refactor the described code for clarity/maintainability "
            "without changing external behavior. All existing tests "
            "must keep passing."
        ),
        "tests": (
            "Add or improve automated tests for the described area. Do "
            "not change production behavior; only add/adjust test files "
            "unless a small testability fix is unavoidable."
        ),
    }

    _AGENTROUTER_HEADERS = {
        "Originator": "codex_cli_rs",
        "Version": "0.101.0",
        "User-Agent": "codex_cli_rs/0.101.0 (Linux; x86_64) RahYar-AIAgent/1.0",
    }

    KNOWN_FACTS = (
        "KNOWN FACTS:\n"
        "- Alembic migrations under alembic/versions/.\n"
        "- tests/ exists; CI runs pytest.\n"
        "- Card-to-card payment stores academy destination card (not PCI CVV).\n"
        "- Chat assistant is read-only.\n"
        "- Agent never pushes/merges to main; only ai/* + optional PR.\n"
    )

    def __init__(self) -> None:
        self.settings = get_settings()
        self.repo = Path(self.settings.AI_AGENT_REPO_PATH).resolve()

    def _has_git(self) -> bool:
        return self.repo.exists() and (self.repo / ".git").exists()

    def _api_key(self) -> str:
        key = self.settings.effective_ai_api_key
        if not key:
            raise AIAgentError(
                "کلید API تنظیم نشده است. AI_AGENT_API_KEY یا AI_API_KEY را بگذارید."
            )
        return key

    def _base_url(self) -> str:
        return self.settings.effective_ai_base_url

    def _model(self) -> str:
        return self.settings.effective_ai_model

    def _write_capable(self) -> bool:
        return self._has_git() or self.settings.github_write_ready

    def _check_enabled(self, *, require_git: bool = False) -> None:
        if not self.settings.AI_AGENT_ENABLED:
            raise AIAgentError(
                "AI Developer Agent خاموش است. AI_AGENT_ENABLED=true بگذارید."
            )
        self._api_key()
        if require_git and not self._write_capable():
            raise AIAgentError(
                "حالت نوشتن کد نیاز به git دارد.\n"
                "روی Render این‌ها را ست کنید:\n"
                "AI_AGENT_WRITE_ENABLED=true\n"
                "GITHUB_TOKEN=<fine-grained PAT با contents:write + pull_requests:write>\n"
                "GITHUB_REPO=mehrshadevilb-cell/RahYar-Academy-Management-System-V14\n"
                "سپس Redeploy."
            )

    def _git(self, *args: str, timeout: int = 120) -> str:
        if not self._has_git():
            raise AIAgentError("Git working tree is not available.")
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            text=True,
            capture_output=True,
            timeout=timeout,
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
                raise AIAgentError("Agent در حال اجرای Task دیگری است. صبر کنید.")
            path.unlink(missing_ok=True)
        path.write_text(f"pid={os.getpid()}\nstarted={time.time()}\n", encoding="utf-8")

    def _release_lock(self) -> None:
        try:
            self._lock_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _reset_worktree(self) -> None:
        if not self._has_git():
            return
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

    def _ensure_git_workspace(self) -> None:
        """Use local git, or clone into work dir when online write is enabled."""
        if self._has_git():
            return
        if not self.settings.github_write_ready:
            raise AIAgentError("Git workspace unavailable and online write is not configured.")

        work = Path(self.settings.AI_AGENT_WORK_DIR).resolve()
        token = (self.settings.GITHUB_TOKEN or "").strip()
        repo_slug = (self.settings.GITHUB_REPO or "").strip().strip("/")
        if "/" not in repo_slug:
            raise AIAgentError("GITHUB_REPO must look like owner/name")

        # Authenticated clone URL — token must never be logged.
        clone_url = f"https://x-access-token:{quote(token, safe='')}@github.com/{repo_slug}.git"

        if work.exists() and (work / ".git").exists():
            self.repo = work
            try:
                self._git("remote", "set-url", "origin", clone_url)
                self._git("fetch", "origin", "main", timeout=180)
                self._git("checkout", "main")
                self._git("reset", "--hard", "origin/main")
            except AIAgentError:
                shutil.rmtree(work, ignore_errors=True)
            else:
                return

        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "50",
                "--branch",
                "main",
                clone_url,
                str(work),
            ],
            text=True,
            capture_output=True,
            timeout=300,
        )
        if result.returncode:
            # Strip token if git echoed the URL in stderr.
            err = (result.stderr or result.stdout or "clone failed").replace(token, "***")
            raise AIAgentError(f"git clone failed: {err[:800]}")

        self.repo = work
        self._git("config", "user.email", "ai-agent@rahyar.local")
        self._git("config", "user.name", "RahYar AI Agent")

    def _push_and_open_pr(self, branch: str, title: str, body: str) -> str:
        if not self.settings.github_write_ready:
            return "(local commit only — set AI_AGENT_WRITE_ENABLED to push PR)"

        self._git("push", "-u", "origin", branch, timeout=180)

        token = (self.settings.GITHUB_TOKEN or "").strip()
        repo_slug = (self.settings.GITHUB_REPO or "").strip()
        payload = json.dumps(
            {"title": title[:200], "head": branch, "base": "main", "body": body[:4000]}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo_slug}/pulls",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "RahYar-AIAgent",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data.get("html_url") or f"PR created on {branch}"
        except urllib.error.HTTPError as exc:
            raw = ""
            try:
                raw = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            # 422 often means PR already exists for the branch.
            if exc.code == 422:
                return f"branch pushed; PR may already exist for {branch} ({raw[:200]})"
            raise AIAgentError(f"GitHub PR API HTTP {exc.code}: {raw}") from exc

    def _is_agentrouter_host(self) -> bool:
        host = (urlparse(self._base_url()).hostname or "").lower()
        return host.endswith("agentrouter.org")

    def _provider_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "RahYar-AIAgent/1.0",
        }
        if self._is_agentrouter_host():
            headers.update(self._AGENTROUTER_HEADERS)
        return headers

    def _ping_provider(self) -> str:
        url = self._base_url().rstrip("/") + "/chat/completions"
        payload = {
            "model": self._model(),
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 8,
            "temperature": 0,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._provider_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=min(30, self.settings.AI_AGENT_TIMEOUT_SECONDS)
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return f"ok content={content!r}"
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                pass
            return f"http_{exc.code} {body or exc.reason}"
        except Exception as exc:
            return f"error {type(exc).__name__}: {exc}"

    def status(self) -> str:
        self._check_enabled(require_git=False)
        write = self._write_capable()
        lines = [
            f"enabled={self.settings.AI_AGENT_ENABLED}",
            f"api_key_configured={bool(self.settings.effective_ai_api_key)}",
            f"model={self._model()}",
            f"base_url={self._base_url()}",
            f"max_retries={self.settings.AI_AGENT_MAX_RETRIES}",
            f"repo={self.repo}",
            f"git_available={self._has_git()}",
            f"github_write_ready={self.settings.github_write_ready}",
            f"write_mode={'yes' if write else 'no (status/analyze only)'}",
            f"chat_assistant_enabled={self.settings.CHAT_ASSISTANT_ENABLED}",
            f"chat_key_configured={bool(self.settings.effective_chat_api_key)}",
        ]
        if self._has_git():
            try:
                lines.extend(
                    [
                        f"branch={self._git('branch', '--show-current')}",
                        f"head={self._git('rev-parse', '--short', 'HEAD')}",
                        f"locked={self._lock_path().exists()}",
                    ]
                )
            except AIAgentError as exc:
                lines.append(f"git_error={exc}")
        elif self.settings.github_write_ready:
            lines.append(
                "note=Online write: clone on demand to AI_AGENT_WORK_DIR, push ai/* + PR"
            )
        else:
            lines.append(
                "note=برای نوشتن کد: AI_AGENT_WRITE_ENABLED + GITHUB_TOKEN + GITHUB_REPO"
            )
        lines.append(f"provider_ping={self._ping_provider()}")
        return "\n".join(lines)

    def _list_tree(self, relative: str, *, limit: int = 200) -> str:
        root = self.repo / relative
        if not root.exists():
            return f"{relative}/: (not present)"
        paths = sorted(
            str(p.relative_to(self.repo))
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix in {".py", ".md", ".yml", ".yaml", ".html", ".txt"}
        )
        body = "\n".join(paths[:limit])
        more = f"\n... ({len(paths) - limit} more)" if len(paths) > limit else ""
        return f"### {relative}/ ({len(paths)} files)\n{body}{more}"

    def _tracked_files(self) -> list[str]:
        """List of repo-relative file paths, via git when available so
        it respects .gitignore, falling back to a directory walk of the
        usual source roots otherwise."""
        if self._has_git():
            try:
                return self._git("ls-files").splitlines()
            except AIAgentError:
                pass
        files: list[str] = []
        for rel in ("src", "tests", "alembic/versions", "docs", ".github/workflows"):
            root = self.repo / rel
            if root.exists():
                files.extend(str(p.relative_to(self.repo)) for p in root.rglob("*") if p.is_file())
        return files

    def _context(self) -> str:
        context_file = self.repo / "AI_PROJECT_CONTEXT.md"
        context = context_file.read_text(encoding="utf-8") if context_file.exists() else ""
        policy_file = self.repo / ".ai-agent" / "policy.md"
        policy = policy_file.read_text(encoding="utf-8") if policy_file.exists() else ""

        if self._has_git():
            try:
                tracked = self._git("ls-files")
            except AIAgentError:
                tracked = "(git ls-files unavailable)"
        else:
            tracked = "\n\n".join(
                self._list_tree(rel)
                for rel in ("src", "tests", "alembic/versions", "docs", ".github/workflows")
            )

        return (
            f"{self.KNOWN_FACTS}\n"
            f"PROJECT CONTEXT:\n{context}\n\n"
            f"AGENT POLICY:\n{policy}\n\n"
            f"REPOSITORY INVENTORY:\n{tracked}"
        )

    def _request_model(self, prompt: str) -> str:
        url = self._base_url().rstrip("/") + "/chat/completions"
        payload = {
            "model": self._model(),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the RahYar senior software engineer. "
                        "Follow project architecture. Never include secrets. "
                        "Return concise engineering output."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._provider_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.settings.AI_AGENT_TIMEOUT_SECONDS
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:800]
            except Exception:
                pass
            raise AIAgentError(
                f"AI provider HTTP {exc.code}: {body or exc.reason}\nurl={url}"
            ) from exc
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
        self._check_enabled(require_git=False)
        self._acquire_lock()
        try:
            status = ""
            if self._has_git():
                try:
                    status = self._git("status", "--short")
                except AIAgentError:
                    status = "(git status unavailable)"
            audit_guidance = """
AUDIT QUALITY CONTRACT:
- Inspect the supplied repository inventory and current git status; do not invent files,
  features, test results, vulnerabilities, or runtime behavior.
- Separate CONFIRMED findings from NEEDS-VERIFICATION observations.
- For every confirmed finding include: severity (P0/P1/P2/P3), exact path, symbol or
  line area, user/business impact, why it is a problem, and the smallest safe fix.
- Prioritize correctness, security/privacy, data integrity, availability, and failing
  tests before style suggestions. Do not report a missing test suite when tests exist.
- Mention evidence and a concrete regression test for each proposed fix.
- End with a compact summary: confirmed count by severity, verification items, and the
  recommended next action. Do not modify files.
""".strip()
            prompt = f"""{self._context()}

CURRENT GIT STATUS:
{status or '(advisory mode)'}

TASK:
{request}

{audit_guidance}
Group findings by severity with paths and remediation.
If tests/ or alembic/versions/ appear in inventory, do NOT report them missing.
Write primarily in Persian; keep paths in English."""
            return self._request_model(prompt)
        finally:
            self._release_lock()

    # ------------------------------------------------------------------
    # Read-only inspection skills — no model call required, no lock
    # needed (nothing is written), safe to run anytime the feature is
    # enabled. Exposed to the owner via admin_ai.py so they can inspect
    # the codebase from Telegram without needing GitHub open.
    # ------------------------------------------------------------------

    def list_ai_branches(self) -> str:
        """Lists ai/* branches (local and, if fetched, origin/ai/*) with
        their last commit date and subject, newest first — visibility
        into everything the agent has previously done."""
        self._check_enabled(require_git=False)
        if not self._has_git():
            return "(git در دسترس نیست — این قابلیت فقط با git workspace کار می‌کند)"
        try:
            raw = self._git(
                "for-each-ref",
                "--sort=-committerdate",
                "--format=%(refname:short)|%(committerdate:short)|%(subject)",
                "refs/heads/ai/",
                "refs/remotes/origin/ai/",
            )
        except AIAgentError as exc:
            return f"(خطا در خواندن شاخه‌ها: {exc})"
        if not raw:
            return "هیچ شاخه‌ی ai/* یافت نشد."
        lines = ["🌿 شاخه‌های AI Agent (جدیدترین اول):"]
        for row in raw.splitlines():
            parts = row.split("|", 2)
            if len(parts) == 3:
                name, date, subject = parts
                lines.append(f"- {name} ({date}): {subject}")
        return "\n".join(lines)

    def read_file(self, relative_path: str, max_chars: int | None = None) -> str:
        """Read-only: return a tracked file's content so the owner can
        inspect it from Telegram. Reuses the same _safe_path guard as
        write operations even though this never writes, so it can never
        read outside the repo or peek at protected/secret paths."""
        self._check_enabled(require_git=False)
        path = self._safe_path(relative_path)
        if not path.exists() or not path.is_file():
            raise AIAgentError(f"فایل پیدا نشد: {relative_path}")
        limit = max_chars or self.MAX_READ_CHARS
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise AIAgentError(f"خطا در خواندن فایل: {exc}") from exc
        truncated = content[:limit]
        remaining = len(content) - limit
        suffix = f"\n... ({remaining} کاراکتر بیشتر، فایل کامل را از GitHub ببینید)" if remaining > 0 else ""
        return f"📄 {relative_path} ({len(content)} کاراکتر)\n\n{truncated}{suffix}"

    def search_code(self, query: str, limit: int = 30) -> str:
        """Read-only, literal (non-regex) case-insensitive search across
        tracked text files. Deliberately not regex: the owner types
        business terms or symbol names, not patterns, and a plain
        substring search has zero ReDoS/injection surface."""
        self._check_enabled(require_git=False)
        needle = (query or "").strip()
        if not needle:
            raise AIAgentError("عبارت جستجو خالی است.")
        if len(needle) < 2:
            raise AIAgentError("عبارت جستجو باید حداقل ۲ کاراکتر باشد.")
        if len(needle) > 200:
            raise AIAgentError("عبارت جستجو خیلی طولانی است.")

        needle_lower = needle.lower()
        matches: list[str] = []
        for rel in self._tracked_files():
            if len(matches) >= limit:
                break
            full = self.repo / rel
            if not full.is_file() or full.suffix not in self.SEARCHABLE_SUFFIXES:
                continue
            try:
                text = full.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if needle_lower in line.lower():
                    matches.append(f"{rel}:{line_number}: {line.strip()[:160]}")
                    if len(matches) >= limit:
                        break

        if not matches:
            return f"🔍 چیزی برای «{needle}» پیدا نشد."
        capped = " (فقط این تعداد اول نمایش داده می‌شود)" if len(matches) >= limit else ""
        header = f"🔍 نتایج جستجو برای «{needle}» — {len(matches)} مورد{capped}:"
        return header + "\n" + "\n".join(matches)

    def _ensure_branch(self, purpose: str) -> str:
        current = self._git("branch", "--show-current")
        if current.startswith("ai/"):
            return current
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in purpose).strip("-")[:45]
        branch = f"ai/{slug or 'maintenance'}-{int(time.time()) % 100000}"
        self._git("switch", "-c", branch)
        return branch

    def _safe_path(self, relative: str) -> Path:
        path = Path(relative)
        normalized = path.as_posix().lstrip("./")
        protected_exact = {name.strip("/") for name in self.PROTECTED}
        protected_prefixes = (".git/",)
        if (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or path.parts[0] == ".git"
            or normalized in protected_exact
            or any(normalized.startswith(prefix) for prefix in protected_prefixes)
        ):
            raise AIAgentError(f"Protected or invalid path: {relative}")
        lowered = normalized.lower()
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
        self._check_enabled(require_git=True)
        self._ensure_git_workspace()
        self._acquire_lock()
        try:
            branch = self._ensure_branch(task)
            task_type = (task_type or "feature").strip().lower()
            if task_type not in self.TASK_INTENTS:
                task_type = "feature"
            intent = self.TASK_INTENTS[task_type]

            max_retries = max(0, int(self.settings.AI_AGENT_MAX_RETRIES))
            last_error = ""

            for attempt in range(max_retries + 1):
                feedback = ""
                if last_error:
                    feedback = (
                        f"\n\nPREVIOUS ATTEMPT FAILED (attempt {attempt}/{max_retries}):\n"
                        f"{last_error}\nProduce a corrected JSON plan."
                    )

                prompt = f"""{self._context()}

TASK TYPE: {task_type}
INTENT: {intent}

TASK:
{task}
{feedback}

Return ONLY valid JSON:
{{"summary": string, "files": [{{"path": string, "content": string}}]}}

Complete file contents, not diffs. Minimum files.
Never include .env/secrets. Never target main."""

                try:
                    raw = self._request_model(prompt)
                    plan = self._parse_plan(raw)
                    written = self._apply_files(plan.get("files", []))
                except AIAgentError as exc:
                    last_error = str(exc)
                    self._reset_worktree()
                    if attempt >= max_retries:
                        return f"Branch: {branch}\nFailed after retries.\n{last_error}"
                    continue

                ok, check_msg = self._run_checks()
                if not ok:
                    last_error = check_msg
                    self._reset_worktree()
                    if attempt >= max_retries:
                        return (
                            f"Branch: {branch}\n"
                            f"Checks failed; not committed.\n{check_msg}"
                        )
                    continue

                self._git("add", "--", *written)
                self._git("commit", "-m", f"ai({task_type}): {task[:60]}")
                head = self._git("rev-parse", "--short", "HEAD")
                pr_info = ""
                try:
                    pr_info = self._push_and_open_pr(
                        branch,
                        title=f"ai({task_type}): {task[:100]}",
                        body=(
                            f"Owner task: {task}\n\n"
                            f"AI Agent summary: {plan.get('summary', '')}\n\n"
                            f"Checks: PASS\nHead: {head}"
                        ),
                    )
                except AIAgentError as exc:
                    pr_info = f"push/PR warning: {exc}"
                return (
                    f"Branch: {branch}\n"
                    f"Changed: {', '.join(written)}\n"
                    f"Commit: {head}\n"
                    f"{pr_info}"
                )

            return f"Branch: {branch}\nFailed."
        finally:
            self._release_lock()
