from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """
    Make DATABASE_URL safe for SQLAlchemy 2 + psycopg3.
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

    BOT_USERNAME: str | None = None

    SITE_NAME: str = "آکادمی راه‌یار"
    SITE_TAGLINE: str = "آموزش حرفه‌ای موسیقی — دوره‌های دیجیتال و کلاس آنلاین"

    # AI Developer Agent
    AI_AGENT_ENABLED: bool = False
    AI_AGENT_REPO_PATH: str = "."
    AI_AGENT_API_KEY: str | None = None
    AI_AGENT_BASE_URL: str = "https://api.openai.com/v1"
    AI_AGENT_MODEL: str = "gpt-5.6"
    AI_AGENT_MAX_RETRIES: int = 2
    AI_AGENT_TIMEOUT_SECONDS: int = 120

    # Simple aliases for external providers
    # Allows Render ENV names:
    # AI_API_KEY, AI_BASE_URL, AI_MODEL
    AI_API_KEY: str | None = None
    AI_BASE_URL: str | None = None
    AI_MODEL: str | None = None

    CHAT_ASSISTANT_ENABLED: bool = False
    CHAT_ASSISTANT_API_KEY: str | None = None
    CHAT_ASSISTANT_BASE_URL: str = "https://api.openai.com/v1"
    CHAT_ASSISTANT_MODEL: str = "gpt-5.6"
    CHAT_ASSISTANT_TIMEOUT_SECONDS: int = 30
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

    @property
    def effective_ai_api_key(self) -> str | None:
        return self.AI_AGENT_API_KEY or self.AI_API_KEY

    @property
    def effective_ai_base_url(self) -> str:
        return self.AI_AGENT_BASE_URL if self.AI_AGENT_API_KEY else (self.AI_BASE_URL or self.AI_AGENT_BASE_URL)

    @property
    def effective_ai_model(self) -> str:
        return self.AI_AGENT_MODEL if self.AI_AGENT_API_KEY else (self.AI_MODEL or self.AI_AGENT_MODEL)

    @property
    def bot_deep_link_base(self) -> str | None:
        if not self.BOT_USERNAME:
            return None
        username = self.BOT_USERNAME.lstrip("@").strip()
        if not username:
            return None
        return f"https://t.me/{username}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
