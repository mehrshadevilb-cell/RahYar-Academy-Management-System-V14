from src.core.config.settings import Settings


def test_agentrouter_stale_mimo_model_uses_supported_fallback():
    settings = Settings(
        AI_BASE_URL="https://co.agentrouter.org/v1",
        AI_MODEL="mimo-v2.5-free",
        AI_FALLBACK_MODEL="gpt-5.5",
    )
    assert settings.effective_ai_model == "gpt-5.5"


def test_non_agentrouter_mimo_model_is_not_rewritten():
    settings = Settings(
        AI_BASE_URL="https://api.example.com/v1",
        AI_MODEL="mimo-v2.5-free",
        AI_FALLBACK_MODEL="gpt-5.5",
    )
    assert settings.effective_ai_model == "mimo-v2.5-free"
