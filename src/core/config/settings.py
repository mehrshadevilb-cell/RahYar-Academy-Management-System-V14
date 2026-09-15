from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
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
    raw = (url or "").strip().rstrip("/")
    if not raw:
        return "https://api.openai.com/v1"
    for suffix in ("/chat/completions", "/v1/chat/completions", "/completions"):
        if raw.lower().endswith(suffix):
            raw = raw[: -len(suffix)].rstrip("/")
    host = (urlparse(raw).hostname or "").lower()
    gateway_hosts = ("agentrouter.org", "co.agentrouter.org", "www.agentrouter.org", "api.orcarouter.ai", "orcarouter.ai", "www.orcarouter.ai")
    if host in gateway_hosts and not raw.endswith("/v1"):
        raw += "/v1"
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

    AI_AGENT_ENABLED: bool = True
    AI_AGENT_REPO_PATH: str = "."
    AI_AGENT_API_KEY: str | None = None
    AI_AGENT_BASE_URL: str = "https://api.openai.com/v1"
    AI_AGENT_MODEL: str = "gpt-4o-mini"
    AI_AGENT_MAX_RETRIES: int = 2
    AI_AGENT_TIMEOUT_SECONDS: int = 180
    AI_API_KEY: str | None = None
    AI_BASE_URL: str | None = None
    AI_MODEL: str | None = None
    AI2_API_KEY: str | None = None
    AI2_BASE_URL: str | None = None
    AI2_MODEL: str | None = None
    AI_PROVIDERS_JSON: str = ""

    # Provider gateway credentials used by the DB bootstrap/discovery layer.
    # They are encrypted before persistence and are never logged or returned by
    # API responses.
    ORCAROUTER_API_KEY: str | None = None
    KIRAAI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    AGENTROUTER_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None

    AI_AGENT_WRITE_ENABLED: bool = False
    AI_AGENT_WORK_DIR: str = "/tmp/rahyar-agent-repo"
    GITHUB_TOKEN: str | None = None
    GITHUB_REPO: str = "mehrshadevilb-cell/RahYar-Academy-Management-System-V14"

    CHAT_ASSISTANT_ENABLED: bool = True
    CHAT_ASSISTANT_API_KEY: str | None = None
    CHAT_ASSISTANT_BASE_URL: str = "https://api.openai.com/v1"
    CHAT_ASSISTANT_MODEL: str = "gpt-4o-mini"
    CHAT_ASSISTANT_TIMEOUT_SECONDS: int = 45
    CHAT_ASSISTANT_MAX_MESSAGES_PER_HOUR: int = 20

    KNOWLEDGE_ENABLED: bool = True
    KNOWLEDGE_GROUP_IDS: str = ""
    KNOWLEDGE_FETCH_INTERVAL_HOURS: int = 24
    KNOWLEDGE_AUTO_QUIZ: bool = True
    KNOWLEDGE_QUIZ_INTERVAL_HOURS: int = 24

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        return normalize_database_url(value) if isinstance(value, str) else value

    @property
    def effective_ai_api_key(self) -> str | None:
        return (self.AI_AGENT_API_KEY or self.AI_API_KEY or "").strip() or None

    @property
    def effective_ai_base_url(self) -> str:
        return normalize_openai_compatible_base_url(self.AI_BASE_URL or self.AI_AGENT_BASE_URL or "https://api.openai.com/v1")

    @property
    def effective_ai_model(self) -> str:
        return (self.AI_MODEL or self.AI_AGENT_MODEL or "gpt-4o-mini").strip()

    @property
    def effective_chat_api_key(self) -> str | None:
        return (self.CHAT_ASSISTANT_API_KEY or self.effective_ai_api_key or "").strip() or None

    @property
    def effective_chat_base_url(self) -> str:
        chat = (self.CHAT_ASSISTANT_BASE_URL or "").strip()
        default_openai = {"https://api.openai.com/v1", "https://api.openai.com", ""}
        if chat.rstrip("/") not in default_openai:
            return normalize_openai_compatible_base_url(chat)
        if self.AI_BASE_URL or self.AI_AGENT_BASE_URL:
            return self.effective_ai_base_url
        return normalize_openai_compatible_base_url(chat or "https://api.openai.com/v1")

    @property
    def effective_chat_model(self) -> str:
        chat_model = (self.CHAT_ASSISTANT_MODEL or "").strip()
        if chat_model and chat_model != "gpt-4o-mini":
            return chat_model
        if self.effective_ai_api_key:
            return self.effective_ai_model
        return chat_model or "gpt-4o-mini"

    @property
    def github_write_ready(self) -> bool:
        return bool(self.AI_AGENT_WRITE_ENABLED and (self.GITHUB_TOKEN or "").strip() and (self.GITHUB_REPO or "").strip())

    @property
    def knowledge_group_ids(self) -> set[int]:
        result: set[int] = set()
        for value in self.KNOWLEDGE_GROUP_IDS.split(","):
            try:
                if value.strip():
                    result.add(int(value.strip()))
            except ValueError:
                continue
        return result

    @property
    def bot_deep_link_base(self) -> str | None:
        if not self.BOT_USERNAME:
            return None
        username = self.BOT_USERNAME.lstrip("@").strip()
        return f"https://t.me/{username}" if username else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
