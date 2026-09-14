from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """
    Make DATABASE_URL safe for SQLAlchemy 2 + psycopg3.

    Render (and many hosts) inject `postgres://` or bare `postgresql://`.
    Our stack uses the psycopg3 driver, so the URL must be
    `postgresql+psycopg://...`. SQLite and already-qualified URLs are
    left unchanged.
    """
    if not url:
        return url

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")

    if url.startswith("postgresql+psycopg://"):
        return url

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")

    return url


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

    # AI Developer Agent. Disabled unless explicitly configured.
    AI_AGENT_ENABLED: bool = False
    AI_AGENT_REPO_PATH: str = "."
    AI_AGENT_API_KEY: str | None = None
    AI_AGENT_BASE_URL: str = "https://api.openai.com/v1"
    AI_AGENT_MODEL: str = "gpt-5.6"
    AI_AGENT_MAX_RETRIES: int = 2
    AI_AGENT_TIMEOUT_SECONDS: int = 120

    # Student-facing chat assistant ("chat with the bot" / onboarding
    # guide). Read-only: it never touches the database or the
    # filesystem, unlike the AI Developer Agent above. Disabled unless
    # explicitly configured, since it calls an external paid API for
    # every message a student sends.
    CHAT_ASSISTANT_ENABLED: bool = False
    CHAT_ASSISTANT_API_KEY: str | None = None
    CHAT_ASSISTANT_BASE_URL: str = "https://api.openai.com/v1"
    CHAT_ASSISTANT_MODEL: str = "gpt-5.6"
    CHAT_ASSISTANT_TIMEOUT_SECONDS: int = 30
    # Safety cap so one confused/abusive user can't run up the API bill.
    CHAT_ASSISTANT_MAX_MESSAGES_PER_HOUR: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_database_url(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
