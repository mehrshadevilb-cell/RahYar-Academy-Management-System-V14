import urllib.error

from src.ai.provider_router import AIProviderRouter


def _clear_settings():
    from src.core.config.settings import get_settings
    get_settings.cache_clear()


def test_ai_and_ai2_env_discovery(monkeypatch):
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


def test_rate_limit_fails_over_to_ai2(monkeypatch):
    monkeypatch.delenv("AI_PROVIDERS_JSON", raising=False)
    monkeypatch.setenv("AI_API_KEY", "primary-key")
    monkeypatch.setenv("AI_BASE_URL", "https://primary.example/v1")
    monkeypatch.setenv("AI_MODEL", "primary-model")
    monkeypatch.setenv("AI2_API_KEY", "secondary-key")
    monkeypatch.setenv("AI2_BASE_URL", "https://secondary.example/v1")
    monkeypatch.setenv("AI2_MODEL", "secondary-model")
    _clear_settings()
    router = AIProviderRouter()
    calls = []

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"choices":[{"message":{"content":"OK"}}]}'

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
    assert result["_rahyar_model"] == "secondary-model"
    assert calls == [
        "https://primary.example/v1/chat/completions",
        "https://secondary.example/v1/chat/completions",
    ]
    assert router._model_cooldown_until["primary:primary-model"] > 0
    _clear_settings()


def test_transient_504_retries_same_model_before_cooldown(monkeypatch):
    monkeypatch.delenv("AI_PROVIDERS_JSON", raising=False)
    monkeypatch.setenv("AI_API_KEY", "primary-key")
    monkeypatch.setenv("AI_BASE_URL", "https://primary.example/v1")
    monkeypatch.setenv("AI_MODEL", "primary-model")
    _clear_settings()
    router = AIProviderRouter()
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"choices":[{"message":{"content":"RECOVERED"}}]}'

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 504, "gateway timeout", {}, None)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = router.chat([{"role": "user", "content": "hello"}])
    assert result["choices"][0]["message"]["content"] == "RECOVERED"
    assert len(calls) == 2
    assert "primary:primary-model" not in router.cooldown_snapshot()
    _clear_settings()
