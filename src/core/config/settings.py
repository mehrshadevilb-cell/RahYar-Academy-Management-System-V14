from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "RahYar Academy Management System"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite:///./rahyar.db"

    BOT_TOKEN: str = ""

    SECRET_KEY: str = ""

    OWNER_ID: int = 0

    PROXY_URL: str | None = None
    REDIS_URL: str | None = None

    DEFAULT_CARD_NUMBER: str | None = None
    DEFAULT_CARD_HOLDER: str | None = None
    SPOTPLAYER_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
