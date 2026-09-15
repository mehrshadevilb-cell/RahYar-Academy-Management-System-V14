import json

from src.ai.provider_router import AIProviderRouter


def test_provider_router_uses_env_key(monkeypatch):
    monkeypatch.setenv("ROUTER_TEST_KEY", "secret-value")
    monkeypatch.setenv(
        "AI_PROVIDERS_JSON",
        json.dumps([
            {
                "name": "free-provider",
                "api_key_env": "ROUTER_TEST_KEY",
                "base_url": "https://example.com/v1",
                "model": "free-model",
                "priority": 10,
            },
            {
                "name": "backup-provider",
                "api_key": "backup-secret",
                "base_url": "https://example.org/v1",
                "model": "backup-model",
                "priority": 20,
            },
        ]),
    )
    router = AIProviderRouter()
    providers = router.providers()
    assert [p.name for p in providers] == ["free-provider", "backup-provider"]
    assert providers[0].api_key == "secret-value"
    assert providers[1].model == "backup-model"


def test_retry_after_from_provider_metadata(monkeypatch):
    monkeypatch.setenv("AI_PROVIDERS_JSON", "[]")
    value = AIProviderRouter._retry_after({}, '{"error":{"metadata":{"retry_after_seconds":42}}}')
    assert value == 42
