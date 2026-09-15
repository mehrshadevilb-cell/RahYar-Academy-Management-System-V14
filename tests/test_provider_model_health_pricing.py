from src.services.provider_model_health_service import ProviderModelHealthService


def test_free_model_is_free_only_when_explicitly_known() -> None:
    assert ProviderModelHealthService.pricing_status({"model_id": "demo:free"}) == "known_free"
    assert ProviderModelHealthService.pricing_status({"model_id": "demo", "pricing_input": 0, "pricing_output": 0}) == "known_free"
    assert ProviderModelHealthService.pricing_status({"model_id": "demo", "pricing_input": 0.1, "pricing_output": 0.2}) == "known_paid"
    assert ProviderModelHealthService.pricing_status({"model_id": "demo"}) == "unknown"


def test_unknown_pricing_does_not_become_free_when_model_is_healthy() -> None:
    row = {"model_id": "demo", "raw_metadata": {}}
    assert ProviderModelHealthService.pricing_status(row) == "unknown"
    assert ProviderModelHealthService._free(row) is False
