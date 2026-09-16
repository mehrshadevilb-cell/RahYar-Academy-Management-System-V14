import asyncio

import pytest

from src.services.ai.model_refresh_scheduler import AIModelRefreshScheduler


def test_scheduler_enforces_safe_minimum_interval(monkeypatch):
    monkeypatch.setenv("AI_MODEL_REFRESH_INTERVAL_SECONDS", "1")
    scheduler = AIModelRefreshScheduler()
    assert scheduler.interval_seconds == 15 * 60


def test_scheduler_uses_configured_interval(monkeypatch):
    monkeypatch.setenv("AI_MODEL_REFRESH_INTERVAL_SECONDS", "1800")
    scheduler = AIModelRefreshScheduler()
    assert scheduler.interval_seconds == 1800


@pytest.mark.asyncio
async def test_run_once_refreshes_catalog_and_reports_selected_model(monkeypatch):
    class FakeModel:
        model_id = "new-free:free"

    class FakeService:
        def __init__(self, db):
            self.db = db

        def sync_all_active_providers(self):
            return [{"provider_id": "p1", "ok": True, "added": 1}]

        def select_working_default(self):
            return FakeModel()

    class FakeDB:
        def close(self):
            pass

    monkeypatch.setattr("src.services.ai.model_refresh_scheduler.SessionLocal", lambda: FakeDB())
    monkeypatch.setattr("src.services.ai.model_refresh_scheduler.AIModelService", FakeService)
    result = await AIModelRefreshScheduler(interval_seconds=900).run_once()
    assert result == {
        "sync": [{"provider_id": "p1", "ok": True, "added": 1}],
        "selected_model": "new-free:free",
    }


def test_stop_cancels_started_task():
    async def scenario():
        scheduler = AIModelRefreshScheduler(interval_seconds=900)
        scheduler.start()
        task = scheduler._task
        assert task is not None
        scheduler.stop()
        await asyncio.sleep(0)
        assert task.cancelled() or task.done()

    asyncio.run(scenario())

@pytest.mark.asyncio
async def test_loop_does_not_refresh_before_interval(monkeypatch):
    scheduler = AIModelRefreshScheduler(interval_seconds=900)
    called = False

    async def fake_run_once():
        nonlocal called
        called = True

    monkeypatch.setattr(scheduler, "run_once", fake_run_once)
    task = asyncio.create_task(scheduler._loop())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert called is False


assert True
