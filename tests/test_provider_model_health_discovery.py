import json

from src.ai.provider_router import AIProviderRouter
from src.services.provider_model_health_service import ProviderModelHealthService


def test_health_service_uses_live_catalog_instead_of_only_configured_models(monkeypatch):
    monkeypatch.setenv("AI_PROVIDERS_JSON", json.dumps([{"name": "provider", "api_key": "key", "base_url": "https://provider.example/v1", "models": ["manually-added-only"]}]))
    from src.core.config.settings import get_settings
    get_settings.cache_clear()
    router = AIProviderRouter()
    monkeypatch.setattr(router, "_from_database", lambda: [])
    service = ProviderModelHealthService(router)

    monkeypatch.setattr(service, "discover", lambda provider, *, timeout_seconds: ([
        {"model_id": "api-model-a", "display_name": "A", "raw_metadata": {}},
        {"model_id": "api-model-b", "display_name": "B", "raw_metadata": {}},
    ], {"status": "ok", "count": 2}))
    calls = []
    monkeypatch.setattr(router, "_test_request", lambda provider, model, timeout: (calls.append(model) or 200, 3, "OK"))

    results = service.test_all(timeout_seconds=9)
    assert [row["model"] for row in results] == ["api-model-a", "api-model-b"]
    assert all(row["discovered"] for row in results)
    assert calls == ["api-model-a", "api-model-b"]
    get_settings.cache_clear()


def test_health_service_falls_back_when_provider_catalog_is_unavailable(monkeypatch):
    monkeypatch.setenv("AI_PROVIDERS_JSON", json.dumps([{"name": "provider", "api_key": "key", "base_url": "https://provider.example/v1", "models": ["manual-a", "manual-b"]}]))
    from src.core.config.settings import get_settings
    get_settings.cache_clear()
    router = AIProviderRouter()
    monkeypatch.setattr(router, "_from_database", lambda: [])
    service = ProviderModelHealthService(router)
    monkeypatch.setattr(service, "discover", lambda provider, *, timeout_seconds: ([], {"status": "http_401"}))
    monkeypatch.setattr(router, "_test_request", lambda provider, model, timeout: (200, 2, "OK"))

    results = service.test_all()
    assert [row["model"] for row in results] == ["manual-a", "manual-b"]
    assert all(not row["discovered"] for row in results)
    get_settings.cache_clear()
