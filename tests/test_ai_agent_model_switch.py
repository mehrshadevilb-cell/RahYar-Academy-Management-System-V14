from src.core.config.settings import Settings


def test_agentrouter_key_selects_agentrouter_and_ai_model(monkeypatch):
    monkeypatch.setenv("AGENTROUTER_API_KEY", "agent-key")
    monkeypatch.setenv("AI_MODEL", "new-agent-model")
    monkeypatch.setenv("AI_AGENT_MODEL", "old-agent-model")
    monkeypatch.delenv("AI_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_BASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.effective_ai_api_key == "agent-key"
    assert settings.effective_ai_base_url == "https://agentrouter.org/v1"
    assert settings.effective_ai_model == "new-agent-model"


def test_explicit_ai_base_url_still_controls_agentrouter_endpoint(monkeypatch):
    monkeypatch.setenv("AGENTROUTER_API_KEY", "agent-key")
    monkeypatch.setenv("AI_BASE_URL", "https://agentrouter.org")
    monkeypatch.setenv("AI_MODEL", "new-agent-model")

    settings = Settings(_env_file=None)

    assert settings.effective_ai_base_url == "https://agentrouter.org/v1"
    assert settings.effective_ai_model == "new-agent-model"


def test_stale_mimo_model_is_replaced_on_agentrouter(monkeypatch):
    monkeypatch.setenv("AGENTROUTER_API_KEY", "agent-key")
    monkeypatch.setenv("AI_MODEL", "mimo-v2.5-free")
    monkeypatch.setenv("AI_FALLBACK_MODEL", "current-fallback")

    settings = Settings(_env_file=None)

    assert settings.effective_ai_model == "current-fallback"
