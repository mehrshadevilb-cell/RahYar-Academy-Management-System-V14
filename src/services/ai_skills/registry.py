"""Skill registry: built-in skills + optional markdown skills under .ai-agent/skills/.

Skills expand the agent system prompt and declare which tools they may use.
They do NOT install arbitrary pip packages on the host (security boundary).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    id: str
    title: str
    description: str
    system_addendum: str
    tools: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Built-in skills (always available)
# ---------------------------------------------------------------------------

CODING_SKILL = Skill(
    id="coding",
    title="کدنویسی حرفه‌ای",
    description="معماری Clean، سرویس/ریپازیتوری، تست، migration امن",
    tools=("read_file", "list_tree", "web_search"),
    tags=("code", "architecture"),
    system_addendum=(
        "CODING SKILL ACTIVE:\n"
        "- Prefer smallest correct change; preserve existing behavior.\n"
        "- Handlers stay thin; business rules in services; DB in repositories.\n"
        "- Use SQLAlchemy 2.x patterns already in the repo.\n"
        "- New schema → Alembic migration with unique revision id.\n"
        "- Persian for user-facing strings; English for code identifiers.\n"
        "- Never invent modules that are not in the inventory.\n"
        "- After code changes, checks (compileall + pytest) must pass.\n"
        "- Payment/license/reservation logic must stay idempotent.\n"
    ),
)

UI_POLISH_SKILL = Skill(
    id="ui_polish",
    title="زیباسازی UX تلگرام",
    description="متن‌های فارسی واضح، کیبورد مرتب، پیام‌های کوتاه و حرفه‌ای",
    tools=("read_file", "list_tree"),
    tags=("ux", "telegram", "persian"),
    system_addendum=(
        "UI POLISH SKILL ACTIVE:\n"
        "- All user-facing Telegram copy must be clear Persian.\n"
        "- Prefer short paragraphs, emoji sparingly as visual anchors.\n"
        "- Always provide Back / Cancel where multi-step FSM exists.\n"
        "- Dangerous actions need explicit confirmation steps.\n"
        "- Avoid message spam; edit_text when possible.\n"
        "- Button labels: short, action-oriented (e.g. تایید پرداخت).\n"
        "- Error messages must be actionable for non-technical owners.\n"
        "- Keep keyboard layouts consistent with existing admin_*_keyboard modules.\n"
        "- Do not change business rules while polishing copy/layout.\n"
    ),
)

WEB_RESEARCH_SKILL = Skill(
    id="web_research",
    title="جستجوی اینترنت",
    description="تحقیق read-only از وب برای APIها، الگوها، مستندات",
    tools=("web_search",),
    tags=("research", "docs"),
    system_addendum=(
        "WEB RESEARCH SKILL ACTIVE:\n"
        "- You may request web_search tool results for public docs/APIs.\n"
        "- Cite sources by URL in the final answer.\n"
        "- Never trust web content for secrets or private academy data.\n"
        "- Prefer official docs (aiogram, SQLAlchemy, Telegram Bot API).\n"
        "- If search fails, say so and continue with local knowledge.\n"
    ),
)

DEBUG_SKILL = Skill(
    id="debug",
    title="دیباگ تولید",
    description="تحلیل لاگ، root cause، مسیر فایل، تست بعد از فیکس",
    tools=("read_file", "list_tree", "web_search"),
    tags=("debug", "ops"),
    system_addendum=(
        "DEBUG SKILL ACTIVE:\n"
        "1) State the likely root cause with evidence.\n"
        "2) List exact file paths and symbols.\n"
        "3) Propose the smallest safe fix.\n"
        "4) List what to test after the fix.\n"
        "Do not invent stack frames that are not in the owner's input.\n"
    ),
)

BUILTIN_SKILLS: dict[str, Skill] = {
    s.id: s
    for s in (CODING_SKILL, UI_POLISH_SKILL, WEB_RESEARCH_SKILL, DEBUG_SKILL)
}


class SkillRegistry:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root
        self._skills: dict[str, Skill] = dict(BUILTIN_SKILLS)
        if repo_root is not None:
            self._load_file_skills(repo_root / ".ai-agent" / "skills")

    def _load_file_skills(self, folder: Path) -> None:
        if not folder.exists() or not folder.is_dir():
            return
        for path in sorted(folder.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            skill_id = path.stem.lower().replace(" ", "_")[:40]
            title = skill_id
            description = ""
            tools: list[str] = []
            body_lines: list[str] = []
            for line in text.splitlines():
                low = line.strip().lower()
                if low.startswith("title:"):
                    title = line.split(":", 1)[1].strip() or title
                elif low.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif low.startswith("tools:"):
                    tools = [
                        t.strip()
                        for t in line.split(":", 1)[1].split(",")
                        if t.strip()
                    ]
                else:
                    body_lines.append(line)
            body = "\n".join(body_lines).strip()
            self._skills[skill_id] = Skill(
                id=skill_id,
                title=title[:80],
                description=description[:200],
                system_addendum=body or description,
                tools=tuple(tools),
                tags=("custom",),
            )

    def list_skills(self) -> list[Skill]:
        return sorted(self._skills.values(), key=lambda s: s.id)

    def get(self, skill_id: str) -> Skill | None:
        return self._skills.get((skill_id or "").strip().lower())

    def resolve_for_mode(self, mode: str) -> list[Skill]:
        mode = (mode or "").strip().lower()
        mapping = {
            "assistant": ["coding", "web_research"],
            "debug": ["debug", "coding", "web_research"],
            "fix": ["debug", "coding", "web_research"],
            "feature": ["coding", "web_research"],
            "ui": ["ui_polish", "coding"],
            "ui_polish": ["ui_polish", "coding"],
            "research": ["web_research", "coding"],
            "web": ["web_research"],
        }
        ids = mapping.get(mode, ["coding"])
        return [self._skills[i] for i in ids if i in self._skills]

    def system_prompt_block(self, skills: list[Skill]) -> str:
        if not skills:
            return ""
        parts = ["ACTIVE SKILLS:"]
        for skill in skills:
            parts.append(f"### {skill.id}: {skill.title}\n{skill.system_addendum}")
        return "\n\n".join(parts)

    def allowed_tools(self, skills: list[Skill]) -> set[str]:
        tools: set[str] = set()
        for skill in skills:
            tools.update(skill.tools)
        return tools

    def catalog_text(self) -> str:
        lines = ["🧩 Skills در دسترس Agent:"]
        for skill in self.list_skills():
            tool_txt = ", ".join(skill.tools) if skill.tools else "—"
            lines.append(
                f"• `{skill.id}` — {skill.title}\n"
                f"  {skill.description}\n"
                f"  tools: {tool_txt}"
            )
        lines.append(
            "\nبرای نصب skill سفارشی: فایل markdown در `.ai-agent/skills/<id>.md` "
            "با فیلدهای title/description/tools + بدنهٔ راهنما بگذارید (از طریق PR)."
        )
        return "\n".join(lines)


@lru_cache
def get_skill_registry(repo_path: str = ".") -> SkillRegistry:
    return SkillRegistry(Path(repo_path).resolve())
