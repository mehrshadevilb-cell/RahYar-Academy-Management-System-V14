import json
import urllib.error

from src.ai.provider_router import AIProviderRouter


def _clear_settings():
    from src.core.config.settings import get_settings
    get_settings.cache_clear()


def test_provider_pool_uses_priority_and_env_keys(monkeypatch):
    monkeypatch.setenv("A_KEY", "secret-a")
    monkeypatch.setenv("B_KEY", "secret-b")
    monkeypatch.setenv(
        "AI_PROVIDERS_JSON",
        json.dumps([
            {"name": "b", "api_key_env": "B_KEY", "base_url": "https://b.example/v1", "model": "b-model", "priority": 20},
            {"name": "a", "api_key_env": "A_KEY", "base_url": "https://a.example/v1", "model": "a-model", "priority": 10},
        ]),
    )
    _clear_settings()
    router = AIProviderRouter()
    assert [p.name for p in router.providers()] == ["a", "b"]
    assert router.providers()[0].api_key == "secret-a"
    _clear_settings()


def test_ai_and_ai2_env_form_automatic_failover(monkeypatch):
    monkeypatch.delenv("AI_PROVIDERS_JSON", raising=False)
    monkeypatch.setenv("AI_API_KEY", "primary-key")
    monkeypatch.setenv("AI_BASE_URL", "https://primary.example/v1")
    monkeypatch.setenv("AI_MODEL", "primary-model")
    monkeypatch.setenv("AI2_API_KEY", "secondary-key")
    monkeypatch.setenv("AI2_BASE_URL", "https://secondary.example/v1")
    monkeypatch.setenv("AI2_MODEL", "secondary-model")
    _clear_settings()
    router = AIProviderRouter()
    assert [p.name for p in router.providers()] == ["primary", "secondary"]
    assert [p.model for p in router.providers()] == ["primary-model", "secondary-model"]
    _clear_settings()


def test_rate_limit_fails_over(monkeypatch):
    monkeypatch.delenv("AI_PROVIDERS_JSON", raising=False)
    monkeypatch.setenv("AI_API_KEY", "a")
    monkeypatch.setenv("AI_BASE_URL", "https://a.example/v1")
    monkeypatch.setenv("AI_MODEL", "a-model")
    monkeypatch.setenv("AI2_API_KEY", "b")
    monkeypatch.setenv("AI2_BASE_URL", "https://b.example/v1")
    monkeypatch.setenv("AI2_MODEL", "b-model")
    _clear_settings()
    router = AIProviderRouter()
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"choices":[{"message":{"content":"OK"}}]}'

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            error = urllib.error.HTTPError(request.full_url, 429, "rate", {}, None)
            error.headers = {"Retry-After": "120"}
            raise error
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = router.chat([{"role": "user", "content": "hello"}])
    assert result["_rahyar_provider"] == "secondary"
    assert calls == [
        "https://a.example/v1/chat/completions",
        "https://b.example/v1/chat/completions",
    ]
    assert router.status()[0]["cooldown_seconds"] > 0
    _clear_settings()
