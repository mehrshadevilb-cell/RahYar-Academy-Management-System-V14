"""Runtime orchestration for the RahYar AI Developer Agent."""

from __future__ import annotations

import asyncio
import json
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from src.database.models.admin_log import AdminLog
from src.database.session import SessionLocal
from src.services.ai_agent_service import AIAgentError, AIAgentService
from src.core.config.settings import get_settings

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover
    redis = None


@dataclass(frozen=True)
class AgentPlan:
    objective: str
    approach: list[str]
    skills: list[str]
    inspect: list[str]
    risks: list[str]
    tests: list[str]


class AIAgentRuntime:
    ALWAYS_SKILLS = ("security.md", "coding.md", "review.md")
    KEYWORD_SKILLS = {
        "telegram_ui.md": ("telegram", "bot", "keyboard", "button", "ui", "ux", "پیام", "دکمه"),
        "ai_ui_design.md": ("ai developer", "dashboard", "agent ui", "agent", "پنل", "داشبورد"),
        "security.md": ("security", "auth", "permission", "secret", "token", "payment", "امنیت", "دسترسی"),
        "coding.md": ("code", "implement", "feature", "refactor", "کد", "قابلیت"),
        "review.md": ("review", "audit", "bug", "fix", "test", "بازبینی", "باگ", "تست"),
    }
    MAX_SKILL_FILES = 6
    MAX_SKILL_CHARS = 18_000
    REDIS_LOCK_KEY = "rahyar:ai-agent:single-flight"
    REDIS_LOCK_TTL = 45 * 60

    def __init__(self, agent: AIAgentService | None = None) -> None:
        self.agent = agent or AIAgentService()
        self.settings = get_settings()
        self._tasks: dict[int, asyncio.Task] = {}
        self._task_labels: dict[int, str] = {}
        self._lock = asyncio.Lock()
        self._redis = None
        if redis is not None and self.settings.REDIS_URL:
            try:
                self._redis = redis.from_url(self.settings.REDIS_URL, decode_responses=True)
            except Exception:
                self._redis = None

    @property
    def skills_dir(self) -> Path:
        return self.agent.repo / ".ai-agent" / "skills"

    def select_skills(self, task: str) -> list[str]:
        text = (task or "").lower()
        selected: list[str] = []
        for name in self.ALWAYS_SKILLS:
            if (self.skills_dir / name).is_file():
                selected.append(name)
        for name, keywords in self.KEYWORD_SKILLS.items():
            if name in selected or len(selected) >= self.MAX_SKILL_FILES:
                continue
            if any(keyword in text for keyword in keywords) and (self.skills_dir / name).is_file():
                selected.append(name)
        return selected[: self.MAX_SKILL_FILES]

    def skill_context(self, task: str) -> str:
        chunks: list[str] = []
        used = 0
        for name in self.select_skills(task):
            path = self.skills_dir / name
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            remaining = self.MAX_SKILL_CHARS - used
            if remaining <= 0:
                break
            content = content[:remaining]
            chunks.append(f"### SKILL: {name}\n{content}")
            used += len(content)
        return "\n\n".join(chunks)

    def _plan_prompt(self, task: str, task_type: str) -> str:
        skills = self.skill_context(task)
        return f"""You are planning a change for the RahYar Academy Management System.
This is READ-ONLY planning: do not modify files.

TASK TYPE: {task_type}
TASK:
{task}

SELECTED ENGINEERING SKILLS:
{skills or '(skills unavailable)'}

Return ONLY JSON in this schema:
{{
  "objective": "short objective",
  "approach": ["ordered implementation steps"],
  "skills": ["skill filenames"],
  "inspect": ["repo paths or symbols to inspect"],
  "risks": ["security/regression/migration risks"],
  "tests": ["tests that must run or be added"]
}}
Keep the plan minimal, specific and safe. Never request secrets."""

    @staticmethod
    def _parse_plan(raw: str) -> AgentPlan:
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIAgentError("Planner returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise AIAgentError("Planner returned an invalid object.")

        def strings(key: str) -> list[str]:
            value = data.get(key, [])
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if str(item).strip()][:12]

        objective = str(data.get("objective", "")).strip()
        if not objective:
            raise AIAgentError("Planner did not return an objective.")
        return AgentPlan(
            objective=objective,
            approach=strings("approach"),
            skills=strings("skills"),
            inspect=strings("inspect"),
            risks=strings("risks"),
            tests=strings("tests"),
        )

    def plan(self, task: str, task_type: str = "feature") -> AgentPlan:
        raw = self.agent._request_model(self._plan_prompt(task, task_type))
        return self._parse_plan(raw)

    def build_implementation_task(self, task: str, task_type: str, plan: AgentPlan) -> str:
        skill_text = self.skill_context(task)
        return f"""ORCHESTRATED TASK

Original owner request:
{task}

Task type: {task_type}

Approved read-only plan:
Objective: {plan.objective}
Approach:
- """ + "\n- ".join(plan.approach or ["Inspect the relevant existing code, implement the smallest safe change, and test it."]) + f"""
Inspect:
- """ + "\n- ".join(plan.inspect or ["the relevant source and tests"]) + f"""
Risks:
- """ + "\n- ".join(plan.risks or ["regression and security exposure"]) + f"""
Required tests:
- """ + "\n- ".join(plan.tests or ["compileall and the full pytest suite"]) + f"""

Selected skills:
{skill_text or '(skills unavailable)'}

Implement this plan. Preserve the existing architecture. Do not expose secrets,
modify protected files, weaken tests, or target main. Return complete file contents
only in the normal agent JSON schema."""

    def _audit(self, user_id: int, action: str, description: str) -> None:
        """Best-effort audit logging: a logging failure must never break the agent."""
        db = SessionLocal()
        try:
            db.add(
                AdminLog(
                    admin_telegram_id=str(user_id),
                    action=action[:50],
                    description=description[:500],
                )
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    async def _acquire_distributed_lock(self) -> str | None:
        if self._redis is None:
            return None
        token = secrets.token_urlsafe(24)
        try:
            acquired = await self._redis.set(
                self.REDIS_LOCK_KEY,
                token,
                nx=True,
                ex=self.REDIS_LOCK_TTL,
            )
            if not acquired:
                raise AIAgentError("یک Task مربوط به AI Agent در instance دیگری در حال اجراست. صبر کنید.")
            return token
        except AIAgentError:
            raise
        except Exception:
            # Redis outage falls back to the per-instance asyncio lock and the
            # existing filesystem guard; local/dev operation remains available.
            self._redis = None
            return None

    async def _release_distributed_lock(self, token: str | None) -> None:
        if not token or self._redis is None:
            return
        script = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        end
        return 0
        """
        try:
            await self._redis.eval(script, 1, self.REDIS_LOCK_KEY, token)
        except Exception:
            pass

    async def run_write(
        self,
        user_id: int,
        task: str,
        task_type: str,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        async with self._lock:
            current = self._tasks.get(user_id)
            if current and not current.done():
                raise AIAgentError("یک Task دیگر برای شما در حال اجراست.")
            task_handle = asyncio.create_task(self._run_write_inner(user_id, task, task_type, progress))
            self._tasks[user_id] = task_handle
            self._task_labels[user_id] = task_type
        try:
            return await task_handle
        finally:
            async with self._lock:
                if self._tasks.get(user_id) is task_handle:
                    self._tasks.pop(user_id, None)
                    self._task_labels.pop(user_id, None)

    async def _run_write_inner(
        self,
        user_id: int,
        task: str,
        task_type: str,
        progress: Callable[[str], Awaitable[None]] | None,
    ) -> str:
        async def report(text: str) -> None:
            if progress:
                await progress(text)

        distributed_token = await self._acquire_distributed_lock()
        self._audit(user_id, "AI_AGENT_START", f"AI Agent started: {task_type} | {task[:350]}")
        try:
            await report("🔎 بررسی ساختار پروژه و انتخاب Skillها...")
            plan = await asyncio.to_thread(self.plan, task, task_type)
            await report("🧠 Planner آماده شد؛ وابستگی‌ها و ریسک‌ها مشخص شدند.")
            await report("✏️ اجرای تغییرات روی branch ایزوله...")
            implementation_task = self.build_implementation_task(task, task_type, plan)
            result = await asyncio.to_thread(self.agent.implement, implementation_task, task_type)
            await report("🧪 compile و pytest و کنترل‌های نهایی انجام شد.")
            self._audit(user_id, "AI_AGENT_SUCCESS", f"AI Agent completed: {result[:400]}")
            return result
        except asyncio.CancelledError:
            self._audit(user_id, "AI_AGENT_FAILURE", "AI Agent task cancelled by owner")
            raise
        except Exception as exc:
            self._audit(user_id, "AI_AGENT_FAILURE", f"AI Agent failed: {type(exc).__name__}: {str(exc)[:420]}")
            raise
        finally:
            await self._release_distributed_lock(distributed_token)

    async def cancel(self, user_id: int) -> bool:
        async with self._lock:
            task = self._tasks.get(user_id)
            if not task or task.done():
                return False
            task.cancel()
            return True

    def active(self, user_id: int) -> bool:
        task = self._tasks.get(user_id)
        return bool(task and not task.done())

    def active_label(self, user_id: int) -> str | None:
        return self._task_labels.get(user_id)


runtime = AIAgentRuntime()
