from src.core.config.settings import Settings, normalize_database_url


def test_normalize_postgres_scheme():
    assert (
        normalize_database_url("postgres://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )


def test_normalize_postgresql_scheme():
    assert (
        normalize_database_url("postgresql://u:p@host/db")
        == "postgresql+psycopg://u:p@host/db"
    )


def test_normalize_already_qualified():
    url = "postgresql+psycopg://u:p@host/db"
    assert normalize_database_url(url) == url


def test_normalize_sqlite_unchanged():
    assert normalize_database_url("sqlite:///./rahyar.db") == "sqlite:///./rahyar.db"


def test_settings_applies_normalizer(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@db.render.com/rahyar")
    # Clear lru_cache so a fresh Settings is built
    from src.core.config import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    s = Settings()
    assert s.DATABASE_URL.startswith("postgresql+psycopg://")
    settings_mod.get_settings.cache_clear()
