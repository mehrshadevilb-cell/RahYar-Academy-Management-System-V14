from src.core.admin_access import is_admin_user
from src.core.config.settings import get_settings


def test_configured_admin_username_is_authorized(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "OWNER_ID", 123456)
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "Hi_all, second_admin")

    assert is_admin_user(999, "Hi_all") is True
    assert is_admin_user(999, "@HI_ALL") is True
    assert is_admin_user(999, "second_admin") is True


def test_owner_remains_authorized(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "OWNER_ID", 123456)
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "Hi_all")

    assert is_admin_user(123456, None) is True


def test_unknown_user_is_rejected(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "OWNER_ID", 123456)
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "Hi_all")

    assert is_admin_user(999, "someone_else") is False


def test_missing_username_is_rejected_for_non_owner(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "OWNER_ID", 123456)
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "Hi_all")

    assert is_admin_user(999, None) is False


# Trigger one-time migration after verifying the main branch still had owner-only checks.
