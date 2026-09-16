from src.ai.provider_router import AIProviderRouter
from src.ai.shared_router import get_shared_router, reset_shared_router


def test_shared_router_is_singleton():
    reset_shared_router()
    a = get_shared_router()
    b = get_shared_router()
    assert a is b
    reset_shared_router()


def test_stale_model_ids_are_skipped(monkeypatch):
    monkeypatch.setenv(
        "AI_PROVIDERS_JSON",
        '[{"name":"p","api_key":"k","base_url":"https://x.example/v1","models":["mimo-v2.5-free","good:free"],"priority":1}]',
    )
    from src.core.config.settings import get_settings

    get_settings.cache_clear()
    router = AIProviderRouter()
    models = [m for _, m in router._ordered_candidates(router.providers())]
    assert "mimo-v2.5-free" not in models
    assert "good:free" in models
    get_settings.cache_clear()


def test_persist_model_cooldown_sets_local_state():
    router = AIProviderRouter()
    router._redis = None
    router._persist_model_cooldown("primary:dead-model", 120)
    snap = router.cooldown_snapshot()
    assert "primary:dead-model" in snap
    assert snap["primary:dead-model"] > 0
    router._clear_model_cooldown("primary:dead-model")
    assert "primary:dead-model" not in router.cooldown_snapshot()
