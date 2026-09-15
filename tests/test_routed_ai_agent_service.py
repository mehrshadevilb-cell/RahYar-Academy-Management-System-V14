from src.services.routed_ai_agent_service import RoutedAIAgentService


class FakeRouter:
    def __init__(self):
        self.calls = []

    def providers(self):
        return [type("Provider", (), {"base_url": "https://free.example/v1", "model": "free-model"})()]

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return {"choices": [{"message": {"content": "OK"}}]}


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


def test_runtime_agent_is_routed():
    from src.services.ai_agent_runtime import runtime
    assert isinstance(runtime.agent, RoutedAIAgentService)
