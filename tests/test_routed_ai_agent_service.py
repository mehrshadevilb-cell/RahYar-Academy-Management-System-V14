from src.services.routed_ai_agent_service import RoutedAIAgentService


class FakeRouter:
    def __init__(self):
        self.calls = []
        self.provider = type("Provider", (), {"name": "fake", "base_url": "https://free.example/v1", "model": "free-model", "models": ("free-model",)})()

    def providers(self):
        return [self.provider]

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return {"choices": [{"message": {"content": "OK"}}]}

    def _ordered_candidates(self, providers):
        return [(self.provider, "free-model")]

    @staticmethod
    def _is_free_model(model):
        return model == "free-model"


def test_routed_agent_uses_provider_router(monkeypatch):
    service = RoutedAIAgentService()
    fake = FakeRouter()
    service.router = fake
    assert service._api_key() == "router-managed"
    assert service._base_url() == "https://free.example/v1"
    assert service._model() == "free-model"
    assert service._request_model("hello") == "OK"
    assert fake.calls
    assert fake.calls[0][1]["temperature"] == 0.1


def test_routed_agent_status_uses_router_without_legacy_ping(monkeypatch):
    service = RoutedAIAgentService()
    fake = FakeRouter()
    service.router = fake
    monkeypatch.setattr(service, "_check_enabled", lambda **kwargs: None)
    monkeypatch.setattr(service, "_write_capable", lambda: False)
    monkeypatch.setattr(service, "_has_git", lambda: False)
    monkeypatch.setattr(service.settings, "AI_AGENT_ENABLED", True, raising=False)
    result = service.status()
    assert "router_candidates=['fake/free-model [free]']" in result
    assert "router_free_candidates=1" in result
    assert "provider_ping=deferred_to_router_request" in result


def test_runtime_agent_is_routed():
    from src.services.ai_agent_runtime import runtime
    assert isinstance(runtime.agent, RoutedAIAgentService)
