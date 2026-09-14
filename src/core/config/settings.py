from functools import lru_cache
from urllib.parse import urlparse

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


def normalize_openai_compatible_base_url(url: str) -> str:
    """Normalize gateway base URL for OpenAI-style /chat/completions.

    AgentRouter and similar gateways expect .../v1 as the base so that
    clients call {base}/chat/completions. Owners often paste the bare
    host (https://agentrouter.org) — append /v1 automatically.
    """
    raw = (url or "").strip().rstrip("/")
    if not raw:
        return "https://api.openai.com/v1"

    # Strip accidental endpoint suffixes the owner may have copied
    for suffix in (
        "/chat/completions",
        "/v1/chat/completions",
        "/completions",
    ):
        if raw.lower().endswith(suffix):
            raw = raw[: -len(suffix)].rstrip("/")

    host = (urlparse(raw).hostname or "").lower()
    gateway_hosts = (
        "agentrouter.org",
        "co.agentrouter.org",
        "www.agentrouter.org",
    )
    if host in gateway_hosts and not raw.endswith("/v1"):
        raw = raw + "/v1"

    return raw


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
    # Primary names: AI_AGENT_*
    # Render-friendly aliases: AI_API_KEY, AI_BASE_URL, AI_MODEL
    AI_AGENT_ENABLED: bool = False
    AI_AGENT_REPO_PATH: str = "."
    AI_AGENT_API_KEY: str | None = None
    AI_AGENT_BASE_URL: str = "https://api.openai.com/v1"
    AI_AGENT_MODEL: str = "gpt-4o-mini"
    AI_AGENT_MAX_RETRIES: int = 2
    AI_AGENT_TIMEOUT_SECONDS: int = 120

    # Aliases accepted from Render / external dashboards (e.g. AgentRouter)
    AI_API_KEY: str | None = None
    AI_BASE_URL: str | None = None
    AI_MODEL: str | None = None

    CHAT_ASSISTANT_ENABLED: bool = False
    CHAT_ASSISTANT_API_KEY: str | None = None
    CHAT_ASSISTANT_BASE_URL: str = "https://api.openai.com/v1"
    CHAT_ASSISTANT_MODEL: str = "gpt-4o-mini"
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
        """API key for AI Developer Agent (AI_AGENT_API_KEY or AI_API_KEY)."""
        return (self.AI_AGENT_API_KEY or self.AI_API_KEY or "").strip() or None

    @property
    def effective_ai_base_url(self) -> str:
        """Base URL for OpenAI-compatible chat/completions.

        Prefer explicit AI_BASE_URL (Render alias) over AI_AGENT_BASE_URL so
        owners can set only AI_API_KEY + AI_BASE_URL + AI_MODEL.
        """
        raw = (self.AI_BASE_URL or self.AI_AGENT_BASE_URL or "https://api.openai.com/v1")
        return normalize_openai_compatible_base_url(raw)

    @property
    def effective_ai_model(self) -> str:
        """Model id for AI Developer Agent (AI_MODEL alias preferred)."""
        return (self.AI_MODEL or self.AI_AGENT_MODEL or "gpt-4o-mini").strip()

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
