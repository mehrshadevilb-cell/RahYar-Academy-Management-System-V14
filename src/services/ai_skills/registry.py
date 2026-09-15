"""Skill registry: built-in skills + optional markdown skills under .ai-agent/skills/.

Skills expand the agent system prompt and declare which tools they may use.
They do NOT install arbitrary pip packages on the host (security boundary).
"""

from __future__ import annotations

from dataclasses import dataclass
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
    title="طراحی و زیباسازی UI تلگرام",
    description="سلسله‌مراتب بصری، کیبورد، کپی فارسی، سفر هنرجو و پنل ادمین",
    tools=("read_file", "list_tree"),
    tags=("ux", "telegram", "persian", "design"),
    system_addendum=(
        "UI / DESIGN SKILL ACTIVE:\n"
        "You are the product designer + UX writer for the RahYar Telegram bot.\n"
        "Goals: clarity, speed, trust, Persian-native copy, consistent keyboards.\n"
        "\n"
        "VISUAL HIERARCHY:\n"
        "- Title line (emoji + screen name) → body → status → CTA.\n"
        "- Short messages; bullets for 3+ items; no text walls.\n"
        "\n"
        "KEYBOARDS:\n"
        "- Short verb-first Persian labels; Back on bottom row.\n"
        "- Confirm/Cancel for destructive actions.\n"
        "- Reuse src/bot/keyboards patterns; keep callback prefixes stable.\n"
        "\n"
        "COPY:\n"
        "- Owner is non-technical; students need step-by-step guidance.\n"
        "- Errors: plain Persian + next action. Never stack traces.\n"
        "\n"
        "CONSTRAINTS:\n"
        "- Do not change business rules, payment approval, or OWNER_ID checks.\n"
        "- Prefer edit_text over message spam.\n"
        "- When writing code for UI, only touch keyboards, handler strings, states.\n"
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


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(t.strip() for t in value.split(",") if t.strip())


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
            if path.name.lower() == "readme.md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            skill_id = path.stem.lower().replace(" ", "_")[:40]
            title = skill_id
            description = ""
            tools: list[str] = []
            tags: list[str] = ["custom"]
            body_lines: list[str] = []
            for line in text.splitlines():
                low = line.strip().lower()
                if low.startswith("title:"):
                    title = line.split(":", 1)[1].strip() or title
                elif low.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif low.startswith("tools:"):
                    tools = list(_split_csv(line.split(":", 1)[1]))
                elif low.startswith("tags:"):
                    tags = list(_split_csv(line.split(":", 1)[1])) or ["custom"]
                else:
                    body_lines.append(line)
            body = "\n".join(body_lines).strip()
            self._skills[skill_id] = Skill(
                id=skill_id,
                title=title[:80],
                description=description[:200],
                system_addendum=body or description,
                tools=tuple(tools),
                tags=tuple(tags),
            )

    def list_skills(self) -> list[Skill]:
        return sorted(self._skills.values(), key=lambda s: s.id)

    def get(self, skill_id: str) -> Skill | None:
        return self._skills.get((skill_id or "").strip().lower())

    def by_tag(self, *tags: str) -> list[Skill]:
        wanted = {t.lower() for t in tags}
        return [
            s
            for s in self.list_skills()
            if wanted.intersection({t.lower() for t in s.tags})
        ]

    def resolve_for_mode(self, mode: str) -> list[Skill]:
        mode = (mode or "").strip().lower()
        mapping = {
            "assistant": ["coding", "web_research"],
            "debug": ["debug", "coding", "web_research"],
            "fix": ["debug", "coding", "web_research"],
            "feature": ["coding", "web_research"],
            "ui": ["ui_polish", "coding"],
            "ui_polish": ["ui_polish", "coding"],
            "design": ["ui_polish", "coding"],
            "research": ["web_research", "coding"],
            "web": ["web_research"],
        }
        ids = mapping.get(mode, ["coding"])
        selected: list[Skill] = []
        seen: set[str] = set()
        for skill_id in ids:
            skill = self._skills.get(skill_id)
            if skill and skill.id not in seen:
                selected.append(skill)
                seen.add(skill.id)

        # UI / design modes automatically attach all design|ux tagged skills
        if mode in {"ui", "ui_polish", "design"}:
            for skill in self.by_tag("design", "ux"):
                if skill.id not in seen:
                    selected.append(skill)
                    seen.add(skill.id)

        return selected

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
            tag_txt = ", ".join(skill.tags) if skill.tags else "—"
            lines.append(
                f"• `{skill.id}` — {skill.title}\n"
                f"  {skill.description}\n"
                f"  tags: {tag_txt}\n"
                f"  tools: {tool_txt}"
            )
        lines.append(
            "\nبرای نصب skill طراحی/UI: فایل `.ai-agent/skills/<id>.md` با "
            "`tags: design, ux` بگذارید تا در حالت 🎨 UI به‌صورت خودکار فعال شود."
        )
        return "\n".join(lines)


@lru_cache
def get_skill_registry(repo_path: str = ".") -> SkillRegistry:
    return SkillRegistry(Path(repo_path).resolve())
