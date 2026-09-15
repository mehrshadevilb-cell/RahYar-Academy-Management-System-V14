import json
from types import SimpleNamespace

from src.ai.provider_router import AIProviderRouter


def _clear_settings():
    from src.core.config.settings import get_settings
    get_settings.cache_clear()


def test_test_models_checks_every_candidate_and_reports_latency(monkeypatch):
    monkeypatch.setenv(
        "AI_PROVIDERS_JSON",
        json.dumps([
            {
                "name": "free-provider",
                "api_key": "free-key",
                "base_url": "https://free.example/v1",
                "models": ["model-free", "model-paid"],
                "priority": 10,
            },
            {
                "name": "paid-provider",
                "api_key": "paid-key",
                "base_url": "https://paid.example/v1",
                "model": "paid-model",
                "priority": 20,
            },
        ]),
    )
    _clear_settings()
    router = AIProviderRouter()
    monkeypatch.setattr(router, "_from_database", lambda: [])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()

    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    results = router.test_models(timeout_seconds=9)

    assert len(results) == 3
    assert all(row["ok"] for row in results)
    assert all(row["latency_ms"] >= 0 for row in results)
    assert [row["model"] for row in results] == ["model-free", "model-paid", "paid-model"]
    assert len(calls) == 3
    assert all(timeout == 9 for _, timeout in calls)
    _clear_settings()


def test_test_models_keeps_failed_model_visible(monkeypatch):
    monkeypatch.setenv(
        "AI_PROVIDERS_JSON",
        json.dumps([
            {
                "name": "provider",
                "api_key": "key",
                "base_url": "https://provider.example/v1",
                "models": ["first-free", "second-free"],
            }
        ]),
    )
    _clear_settings()
    router = AIProviderRouter()
    monkeypatch.setattr(router, "_from_database", lambda: [])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/chat/completions"):
            body = json.loads(request.data.decode())
            if body["model"] == "first-free":
                from urllib.error import HTTPError
                raise HTTPError(request.full_url, 429, "rate limited", {"Retry-After": "17"}, None)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    results = router.test_models()

    assert results[0]["model"] == "first-free"
    assert results[0]["ok"] is False
    assert results[0]["status"] == "http_429"
    assert results[0]["retry_after"] == 17
    assert results[1]["model"] == "second-free"
    assert results[1]["ok"] is True
    _clear_settings()
