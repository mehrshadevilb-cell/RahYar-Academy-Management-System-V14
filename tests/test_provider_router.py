import json

from src.ai.provider_router import AIProvider, AIProviderRouter


def _clear_settings():
    from src.core.config.settings import get_settings
    get_settings.cache_clear()


def test_provider_router_uses_env_key(monkeypatch):
    monkeypatch.setenv("ROUTER_TEST_KEY", "secret-value")
    monkeypatch.setenv("AI_PROVIDERS_JSON", json.dumps([{"name": "free-provider", "api_key_env": "ROUTER_TEST_KEY", "base_url": "https://example.com/v1", "model": "free-model", "priority": 10}, {"name": "backup-provider", "api_key": "backup-secret", "base_url": "https://example.org/v1", "model": "backup-model", "priority": 20}]))
    _clear_settings()
    router = AIProviderRouter()
    providers = router.providers()
    assert [p.name for p in providers] == ["free-provider", "backup-provider"]
    assert providers[0].api_key == "secret-value"
    assert providers[1].model == "backup-model"
    _clear_settings()


def test_retry_after_from_provider_metadata(monkeypatch):
    monkeypatch.setenv("AI_PROVIDERS_JSON", "[]")
    _clear_settings()
    value = AIProviderRouter._retry_after({}, '{"error":{"metadata":{"retry_after_seconds":42}}}')
    assert value == 42
    _clear_settings()


def test_free_models_are_globally_before_paid_models(monkeypatch):
    monkeypatch.setenv("AI_PROVIDERS_JSON", json.dumps([{"name": "paid-first-provider", "api_key": "paid-key", "base_url": "https://paid.example/v1", "models": ["paid-model"], "priority": 1}, {"name": "free-provider", "api_key": "free-key", "base_url": "https://free.example/v1", "models": ["backup:free"], "priority": 50}]))
    _clear_settings()
    router = AIProviderRouter()
    candidates = router._ordered_candidates(router.providers())
    assert [model for _, model in candidates] == ["backup:free", "paid-model"]
    _clear_settings()


def test_free_model_is_detected_from_id():
    assert AIProviderRouter._is_free_model("provider/model:free") is True
    assert AIProviderRouter._is_free_model("provider/model-free") is True
    assert AIProviderRouter._is_free_model("provider/model") is False


def test_legacy_env_routes_remain_available_with_db_routes(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "fresh-env-key")
    monkeypatch.setenv("AI_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("AI_MODEL", "env-free-model")
    monkeypatch.setenv("AI_PROVIDERS_JSON", "[]")
    _clear_settings()
    router = AIProviderRouter()
    router._from_database = lambda: [AIProvider(name="database-provider", api_key="old-db-key", base_url="https://db.example.com/v1", models=("db-model",), priority=0)]
    providers = router.providers()
    assert any(p.name == "primary" and p.api_key == "fresh-env-key" for p in providers)
    assert any(p.name == "database-provider" for p in providers)
    _clear_settings()


def test_base_url_is_normalized_for_gateway_env(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "key")
    monkeypatch.setenv("AI_BASE_URL", "https://api.orcarouter.ai")
    monkeypatch.setenv("AI_MODEL", "free-model")
    monkeypatch.setenv("AI_PROVIDERS_JSON", "[]")
    _clear_settings()
    router = AIProviderRouter()
    router._from_database = lambda: []
    providers = router.providers()
    assert providers[0].base_url == "https://api.orcarouter.ai/v1"
    _clear_settings()


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_google_chat_uses_generate_content(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        return _FakeResponse({"candidates": [{"content": {"parts": [{"text": "{\"ok\":true}"}]}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    router = AIProviderRouter()
    provider = AIProvider("google", "google-secret", "https://generativelanguage.googleapis.com/v1beta", ("gemini-test",), provider_type="google")
    data = router._request(provider, "gemini-test", [{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}], {"temperature": 0.2, "max_tokens": 20}, 5)
    assert ":generateContent?key=" in captured["url"]
    assert captured["body"]["generationConfig"]["maxOutputTokens"] == 20
    assert "choices" not in data


def test_anthropic_chat_uses_messages_api(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        return _FakeResponse({"content": [{"type": "text", "text": "hello"}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    router = AIProviderRouter()
    provider = AIProvider("anthropic", "anthropic-secret", "https://api.anthropic.com/v1", ("claude-test",), provider_type="anthropic")
    data = router._request(provider, "claude-test", [{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}], {"temperature": 0.2, "max_tokens": 20}, 5)
    assert captured["url"].endswith("/messages")
    assert captured["body"]["max_tokens"] == 20
    assert captured["body"]["system"] == "system"
    assert data["content"][0]["text"] == "hello"
