"""In-memory activity log for the AI Developer Agent."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentActivity:
    kind: str = "idle"
    mode: str = ""
    request: str = ""
    status: str = "idle"
    started_at: float | None = None
    finished_at: float | None = None
    steps: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    branch: str = ""
    pr_url: str = ""
    outcome: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mode": self.mode,
            "request": self.request[:1500],
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": self.steps[-40:],
            "tools_used": self.tools_used[-20:],
            "files_changed": self.files_changed[:30],
            "branch": self.branch,
            "pr_url": self.pr_url,
            "outcome": self.outcome[:2000],
            "error": self.error[:1000],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentActivity:
        return cls(
            kind=str(data.get("kind") or "idle"),
            mode=str(data.get("mode") or ""),
            request=str(data.get("request") or ""),
            status=str(data.get("status") or "idle"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            steps=list(data.get("steps") or []),
            tools_used=list(data.get("tools_used") or []),
            files_changed=list(data.get("files_changed") or []),
            branch=str(data.get("branch") or ""),
            pr_url=str(data.get("pr_url") or ""),
            outcome=str(data.get("outcome") or ""),
            error=str(data.get("error") or ""),
        )


class ActivityTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current = AgentActivity()
        self._last = AgentActivity()

    def start(self, *, kind: str, mode: str, request: str) -> None:
        with self._lock:
            self._current = AgentActivity(
                kind=kind,
                mode=mode,
                request=(request or "")[:1500],
                status="running",
                started_at=time.time(),
            )
            self._current.steps.append(
                f"شروع شد · نوع={kind} · حالت={mode or '—'}"
            )

    def step(self, message: str) -> None:
        with self._lock:
            if self._current.status != "running":
                return
            self._current.steps.append(message[:300])

    def tool(self, name: str, arg: str = "") -> None:
        with self._lock:
            if self._current.status != "running":
                return
            label = f"tool:{name}"
            if arg:
                label += f"({arg[:80]})"
            self._current.tools_used.append(label)
            self._current.steps.append(
                f"🧰 {name}" + (f" → {arg[:80]}" if arg else "")
            )

    def finish(
        self,
        *,
        success: bool,
        outcome: str = "",
        error: str = "",
        pr_url: str = "",
        cancelled: bool = False,
        persist_dir: Path | None = None,
    ) -> None:
        with self._lock:
            if cancelled:
                self._current.status = "cancelled"
            else:
                self._current.status = "success" if success else "failed"
            self._current.finished_at = time.time()
            self._current.outcome = (outcome or "")[:2000]
            self._current.error = (error or "")[:1000]
            if pr_url:
                self._current.pr_url = pr_url
            if cancelled:
                self._current.steps.append("🛑 لغو شد")
            elif success:
                self._current.steps.append("✅ تمام شد")
            else:
                self._current.steps.append(
                    f"❌ ناموفق: {(error or outcome)[:120]}"
                )
            self._last = AgentActivity(**self._current.__dict__)
            snapshot = self._last
        if persist_dir is not None:
            self._persist(persist_dir, snapshot)

    def _persist(self, repo: Path, activity: AgentActivity) -> None:
        try:
            folder = repo / ".ai-agent"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "last_activity.json"
            path.write_text(
                json.dumps(activity.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def load_persisted(self, repo: Path) -> None:
        path = repo / ".ai-agent" / "last_activity.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self._lock:
                if self._current.status != "running":
                    self._last = AgentActivity.from_dict(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    def report_text(self) -> str:
        with self._lock:
            current = AgentActivity(**self._current.__dict__)
            last = AgentActivity(**self._last.__dict__)

        lines: list[str] = ["👁 فعالیت Agent", ""]

        if current.status == "running":
            elapsed = int(time.time() - (current.started_at or time.time()))
            lines.append("🔴 الان در حال اجراست")
            lines.append(f"نوع: {current.kind} | حالت: {current.mode or '—'}")
            lines.append(f"زمان سپری‌شده: ~{elapsed} ثانیه")
            lines.append("")
            lines.append("📌 درخواست شما:")
            lines.append((current.request or "—")[:500])
            lines.append("")
            lines.append("مراحل تا الان:")
            for i, step in enumerate(current.steps[-15:], start=1):
                lines.append(f"{i}. {step}")
            if current.tools_used:
                lines.append("")
                lines.append("ابزار/مهارت: " + ", ".join(current.tools_used[-8:]))
            lines.append("")
            lines.append("چند ثانیه بعد دوباره همین دکمه را بزنید.")
            return "\n".join(lines)

        target = last if last.status in {"success", "failed", "cancelled"} else current
        if target.status in {"idle", ""} and not target.request:
            lines.append("هنوز Taskی ثبت نشده است.")
            lines.append("بعد از دستیار / دیباگ / Feature / UI این بخش پر می‌شود.")
            return "\n".join(lines)

        status_icon = {
            "success": "✅",
            "failed": "❌",
            "cancelled": "🛑",
        }.get(target.status, "⚪")
        lines.append(f"{status_icon} آخرین اجرا: {target.status}")
        lines.append(f"نوع: {target.kind} | حالت: {target.mode or '—'}")
        if target.started_at and target.finished_at:
            lines.append(
                f"مدت: ~{int(target.finished_at - target.started_at)} ثانیه"
            )
        lines.append("")
        lines.append("📌 چیزی که خواستید:")
        lines.append((target.request or "—")[:700])
        lines.append("")
        lines.append("📋 آیا انجام شد؟")
        if target.status == "success":
            lines.append("بله — Agent کار را تمام کرد.")
        elif target.status == "failed":
            lines.append("خیر — با خطا متوقف شد.")
            if target.error:
                lines.append(f"خطا: {target.error[:400]}")
        elif target.status == "cancelled":
            lines.append("لغو شد — کار نیمه‌کاره رها شد.")
        else:
            lines.append("نامشخص / ناتمام.")

        if target.outcome:
            lines.append("")
            lines.append("نتیجه خلاصه:")
            lines.append(target.outcome[:900])

        if target.steps:
            lines.append("")
            lines.append("مراحل:")
            for i, step in enumerate(target.steps[-20:], start=1):
                lines.append(f"{i}. {step}")

        if target.tools_used:
            lines.append("")
            lines.append("مهارت/ابزار: " + ", ".join(target.tools_used[-10:]))

        if target.files_changed:
            lines.append("")
            lines.append("فایل‌های تغییر یافته:")
            for path in target.files_changed[:15]:
                lines.append(f"• {path}")

        if target.branch:
            lines.append(f"\nbranch: {target.branch}")
        if target.pr_url:
            lines.append(f"PR: {target.pr_url}")

        return "\n".join(lines)


activity_tracker = ActivityTracker()
