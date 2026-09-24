import json
import urllib.error

from src.ai.provider_router import AIProvider, AIProviderRouter
from src.core.config.provider_url_safety import looks_like_api_key, validate_provider_base_url
from src.services.provider_model_health_service import ProviderModelHealthService


def test_api_key_cannot_be_used_as_base_url():
    assert looks_like_api_key("gsk_1234567890abcdefghijklmnopqrstuvwxyz")
    assert validate_provider_base_url("gsk_1234567890abcdefghijklmnopqrstuvwxyz/models") == ""


def test_missing_and_invalid_base_urls_are_non_throwing():
    assert validate_provider_base_url("") == ""
    assert validate_provider_base_url("not-a-url") == ""
    assert validate_provider_base_url("ftp://example.com/v1") == ""
    assert validate_provider_base_url("https://api.example.com/v1") == "https://api.example.com/v1"


def test_models_discovery_failure_is_isolated_and_does_not_raise(monkeypatch):
    router = AIProviderRouter()
    service = ProviderModelHealthService(router)
    provider = AIProvider("broken", "secret", "gsk_bad/models", ("model",), priority=1)
    models, status = service.discover(provider, timeout_seconds=5)
    assert models == []
    assert status["status"] == "invalid_base_url"


def test_discovery_timeout_is_isolated(monkeypatch):
    router = AIProviderRouter()
    service = ProviderModelHealthService(router)
    provider = AIProvider("slow", "secret", "https://slow.example/v1", (), priority=1)
    def fail(*args, **kwargs):
        raise TimeoutError("timed out")
    monkeypatch.setattr("urllib.request.urlopen", fail)
    models, status = service.discover(provider, timeout_seconds=5)
    assert models == []
    assert status["status"].startswith("discovery_failed:")


def test_http_failures_are_quarantined(monkeypatch):
    router = AIProviderRouter()
    service = ProviderModelHealthService(router)
    provider = AIProvider("broken", "secret-key", "https://broken.example/v1", ("model",), priority=1)
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("https://broken.example/v1/models", 429, "rate", {"Retry-After": "12"}, None)
    monkeypatch.setattr("urllib.request.urlopen", fail)
    models, status = service.discover(provider, timeout_seconds=5)
    assert models == []
    assert status["status"] == "http_429"
    assert router.cooldown_snapshot()["broken:__discovery__"] > 0


def test_no_api_key_leak_in_discovery_errors(monkeypatch):
    router = AIProviderRouter()
    service = ProviderModelHealthService(router)
    secret = "gsk_super_secret_value_123456789"
    provider = AIProvider("broken", secret, "https://broken.example/v1", (), priority=1)
    def fail(*args, **kwargs):
        raise urllib.error.URLError(f"request failed with {secret}")
    monkeypatch.setattr("urllib.request.urlopen", fail)
    _, status = service.discover(provider, timeout_seconds=5)
    assert secret not in json.dumps(status)


def test_invalid_provider_is_skipped_before_network(monkeypatch):
    monkeypatch.setenv("AI_PROVIDERS_JSON", json.dumps([
        {"name": "bad", "api_key": "gsk_bad", "base_url": "gsk_bad/models", "model": "bad-model"},
        {"name": "good", "api_key": "good-key", "base_url": "https://good.example/v1", "model": "good-model"},
    ]))
    from src.core.config.settings import get_settings
    get_settings.cache_clear()
    providers = AIProviderRouter().providers()
    assert all(p.name != "bad" for p in providers)
    assert any(p.name == "good" for p in providers)
    get_settings.cache_clear()
