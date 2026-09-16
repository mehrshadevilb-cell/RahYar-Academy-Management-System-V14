"""Speed and intelligence helpers for the RahYar AI Developer Agent."""

from __future__ import annotations


# Task types that should prioritize the debug skill and a tighter context budget.
FAST_FIX_TYPES = frozenset({"fix"})

# Keywords that pull debug.md even for feature tasks phrased as incidents.
DEBUG_KEYWORDS = (
    "bug",
    "error",
    "exception",
    "traceback",
    "stack",
    "crash",
    "fix",
    "broken",
    "regression",
    "500",
    "باگ",
    "خطا",
    "خرابی",
    "اصلاح",
)


def wants_debug_skill(task: str, task_type: str = "feature") -> bool:
    if task_type in FAST_FIX_TYPES:
        return True
    text = (task or "").lower()
    return any(token in text for token in DEBUG_KEYWORDS)


def skill_budget_chars(task_type: str, task: str) -> int:
    """Tighter context for fix tasks improves latency without losing guardrails."""
    if wants_debug_skill(task, task_type):
        return 12_000
    return 18_000


def ordered_skills_for_task(task: str, task_type: str, available: list[str]) -> list[str]:
    """Prefer security/coding/review/debug first for fix-oriented work."""
    preferred = ["security.md", "coding.md", "review.md", "debug.md"]
    selected: list[str] = []
    for name in preferred:
        if name in available and name not in selected:
            if name == "debug.md" and not wants_debug_skill(task, task_type):
                continue
            selected.append(name)
    for name in available:
        if name not in selected:
            selected.append(name)
    return selected
