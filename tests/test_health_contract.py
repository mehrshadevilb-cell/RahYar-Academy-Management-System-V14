import asyncio

from src.core.diagnostics.health import build_health_report


def test_health_marks_optional_dependencies_disabled_when_not_configured(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    report = asyncio.run(build_health_report("test-build"))
    assert report["checks"]["redis"] == "disabled"
    assert report["checks"]["telegram"] in {"ok", "disabled"}
    assert report["ok"] is True


def test_health_is_unhealthy_when_configured_redis_is_unreachable(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    report = asyncio.run(build_health_report("test-build"))
    assert report["checks"]["redis"] == "error"
    assert report["ok"] is False
