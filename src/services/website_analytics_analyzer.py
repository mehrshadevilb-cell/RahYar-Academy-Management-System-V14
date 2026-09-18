"""AI-powered website analytics and growth diagnostics for RahYar.

The collector stays privacy-first: no raw IP/user-agent is persisted. This
service aggregates SiteEvent rows and asks the same live routed AI pool used by
the developer agent for parallel specialist analysis, then a synthesis pass.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from src.database.models.site_event import SiteEvent
from src.database.models.admin_log import AdminLog
from src.database.models.user import User, UserRole
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import EnrollmentStatus, OnlineEnrollment
from src.services.routed_ai_agent_service import RoutedAIAgentService


class WebsiteAnalyticsAnalyzer:
    def __init__(self, agent: RoutedAIAgentService | None = None) -> None:
        self.agent = agent or RoutedAIAgentService()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def snapshot(self, db: Session, days: int = 30) -> dict:
        days = max(1, min(int(days), 365))
        now = self._now()
        since = now - timedelta(days=days)
        previous_since = since - timedelta(days=days)

        def count(event_type: str, start: datetime, end: datetime = now) -> int:
            return int(
                db.query(func.count(SiteEvent.id))
                .filter(
                    SiteEvent.event_type == event_type,
                    SiteEvent.created_at >= start,
                    SiteEvent.created_at < end,
                )
                .scalar()
                or 0
            )

        page_views = count("page_view", since)
        previous_views = count("page_view", previous_since, since)
        unique_visitors = int(
            db.query(func.count(func.distinct(SiteEvent.visitor_hash)))
            .filter(SiteEvent.event_type == "page_view", SiteEvent.created_at >= since)
            .scalar()
            or 0
        )
        top_paths = db.query(
            SiteEvent.path,
            func.count(SiteEvent.id).label("count"),
        ).filter(
            SiteEvent.event_type == "page_view",
            SiteEvent.created_at >= since,
        ).group_by(SiteEvent.path).order_by(desc("count")).limit(20).all()

        event_rows = db.query(
            SiteEvent.event_type,
            func.count(SiteEvent.id).label("count"),
        ).filter(SiteEvent.created_at >= since).group_by(SiteEvent.event_type).order_by(desc("count")).limit(40).all()

        conversions = {
            "orders_started": count("order_start", since),
            "orders_created": count("order_created", since),
            "checkout": count("checkout", since),
            "class_inquiries": count("class_inquiry", since),
            "bot_clicks": count("bot_click", since),
            "ai_chats": count("ai_chat", since),
            "ai_errors": count("ai_error", since),
        }
        for event_name in ("order_start", "order_created", "checkout", "class_inquiry", "bot_click"):
            if conversions[event_name] == 0:
                # Existing deployments may use suffixed event names.
                conversions[event_name] = sum(
                    int(row.count)
                    for row in event_rows
                    if str(row.event_type).startswith(event_name)
                )

        users = int(db.query(func.count(User.id)).filter(User.role == UserRole.STUDENT).scalar() or 0)
        active_classes = int(db.query(func.count(OnlineCourse.id)).filter(OnlineCourse.is_active.is_(True)).scalar() or 0)
        active_enrollments = int(db.query(func.count(OnlineEnrollment.id)).filter(OnlineEnrollment.status == EnrollmentStatus.ACTIVE).scalar() or 0)
        ai_admin_events = int(
            db.query(func.count(AdminLog.id))
            .filter(AdminLog.created_at >= since, AdminLog.action.ilike("%ai%"))
            .scalar() or 0
        )

        attribution: dict[str, int] = {}
        devices: dict[str, int] = {}
        timing_rows = db.query(SiteEvent.event_metadata).filter(
            SiteEvent.event_type.in_(("page_view", "page_timing")),
            SiteEvent.created_at >= since,
        ).limit(10000).all()
        for (metadata,) in timing_rows:
            if not isinstance(metadata, dict):
                continue
            for key in ("utm_source", "utm_medium", "utm_campaign", "referrer"):
                value = str(metadata.get(key) or "").strip()[:120]
                if value:
                    bucket = f"{key}:{value}"
                    attribution[bucket] = attribution.get(bucket, 0) + 1
            device = str(metadata.get("device") or "").strip()
            if device:
                devices[device] = devices.get(device, 0) + 1

        growth = None
        if previous_views:
            growth = round((page_views - previous_views) / previous_views * 100, 2)

        return {
            "period_days": days,
            "generated_at": now.isoformat(),
            "traffic": {
                "page_views": page_views,
                "unique_visitors": unique_visitors,
                "previous_period_page_views": previous_views,
                "page_view_change_percent": growth,
                "top_paths": [{"path": str(path), "count": int(value)} for path, value in top_paths],
                "top_attribution": [{"source": key, "count": value} for key, value in sorted(attribution.items(), key=lambda item: item[1], reverse=True)[:20]],
                "devices": devices,
            },
            "events": [{"event": str(event_type), "count": int(value)} for event_type, value in event_rows],
            "conversion": conversions,
            "education": {
                "students": users,
                "active_classes": active_classes,
                "active_enrollments": active_enrollments,
            },
            "ai": {
                "website_chats": conversions["ai_chats"],
                "errors": conversions["ai_errors"],
                "admin_ai_events": ai_admin_events,
            },
        }

    def _specialist_prompt(self, role: str, snapshot: dict) -> str:
        return f"""You are the {role} specialist for the RahYar/ArtistYar website.
Analyze ONLY the supplied anonymous analytics snapshot. Do not invent traffic sources,
users, demographics, revenue, or causes that are not evidenced.
Return concise JSON with:
- findings: up to 5 evidence-based observations
- anomalies: up to 5 unusual signals
- actions: up to 5 concrete tests or engineering/content actions
- metrics_to_watch: up to 5 metrics
Snapshot:
{json.dumps(snapshot, ensure_ascii=False)}"""

    def analyze(self, db: Session, days: int = 30) -> dict:
        snapshot = self.snapshot(db, days)
        roles = (
            "traffic and acquisition analyst",
            "conversion funnel and UX analyst",
            "technical performance and reliability analyst",
        )

        import concurrent.futures
        specialist_outputs: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="ra-analytics") as pool:
            futures = [pool.submit(self.agent._request_model, self._specialist_prompt(role, snapshot)) for role in roles]
            for future in futures:
                try:
                    specialist_outputs.append(future.result())
                except Exception as exc:
                    specialist_outputs.append(json.dumps({
                        "findings": [], "anomalies": [f"specialist_unavailable:{type(exc).__name__}"],
                        "actions": [], "metrics_to_watch": [],
                    }))

        synthesis_prompt = f"""You are the lead RahYar website analytics agent.
Synthesize the three specialist reports below against the anonymous snapshot.
Separate confirmed observations from hypotheses. Never invent data.
Return JSON:
{{
  "summary": "short Persian summary",
  "priority_findings": [{{"severity":"P0|P1|P2|P3","finding":"...","evidence":"..."}}],
  "experiments": ["..."],
  "engineering_checks": ["..."],
  "content_ux_checks": ["..."],
  "metrics": ["..."]
}}
SNAPSHOT:
{json.dumps(snapshot, ensure_ascii=False)}
SPECIALISTS:
{json.dumps(specialist_outputs, ensure_ascii=False)}"""
        try:
            synthesis = self.agent._request_model(synthesis_prompt)
        except Exception as exc:
            synthesis = json.dumps({
                "summary": "تحلیل AI موقتاً در دسترس نیست.",
                "priority_findings": [],
                "experiments": [],
                "engineering_checks": [f"ai_unavailable:{type(exc).__name__}"],
                "content_ux_checks": [],
                "metrics": ["page_views", "unique_visitors"],
            }, ensure_ascii=False)

        return {
            "ok": True,
            "snapshot": snapshot,
            "specialists": specialist_outputs,
            "synthesis": synthesis,
            "mode": "parallel-specialists+lead-synthesis",
        }
