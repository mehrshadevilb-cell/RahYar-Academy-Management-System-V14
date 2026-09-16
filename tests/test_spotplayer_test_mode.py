from src.integrations.spotplayer.client import SpotPlayerClient
from src.services.license_service import LicenseService


def test_client_accepts_test_flag():
    client = SpotPlayerClient(api_key="dummy")
    assert hasattr(client, "create_license")


def test_license_service_test_mode_helper(monkeypatch):
    service = LicenseService()
    monkeypatch.setattr(service.settings, "SPOTPLAYER_TEST_MODE", True)
    assert service._use_test_mode(None) is True
    assert service._use_test_mode(False) is False
    assert service._use_test_mode(True) is True
    monkeypatch.setattr(service.settings, "SPOTPLAYER_TEST_MODE", False)
    assert service._use_test_mode(None) is False
