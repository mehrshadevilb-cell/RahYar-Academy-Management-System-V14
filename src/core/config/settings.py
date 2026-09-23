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
    gateway_hosts = (
        "agentrouter.org", "co.agentrouter.org", "www.agentrouter.org",
        "api.orcarouter.ai", "orcarouter.ai", "www.orcarouter.ai",
    )
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
    ADMIN_USERNAMES: str = "Hi_all"
    NEW_MEMBER_NOTIFICATION_CHAT_ID: int = 0
    PROXY_URL: str | None = None
    REDIS_URL: str | None = None
    DEFAULT_CARD_NUMBER: str | None = None
    DEFAULT_CARD_HOLDER: str | None = None
    SPOTPLAYER_API_KEY: str | None = None
    BOT_USERNAME: str | None = "Mb_tutorialbot"
    TELEGRAM_WEB_APP_URL: str | None = None
    SITE_NAME: str = "آکادمی راه‌یار"
    SITE_TAGLINE: str = "آموزش حرفه‌ای موسیقی — دوره‌های دیجیتال و کلاس آنلاین"
    WEB_ADMIN_API_KEY: str = ""
    WEB_STUDENT_BRIDGE_SECRET: str = ""
    ANALYTICS_HASH_SECRET: str = ""

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
    AI_FALLBACK_MODEL: str = "gpt-5.5"
    AI_PROVIDERS_JSON: str = ""
    AI_DB_ONLY: bool = True

    # Broad provider env catalog. Secrets stay in Render; never commit values.
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str | None = None
    ORCAROUTER_API_KEY: str | None = None
    ORCAROUTER_BASE_URL: str = "https://api.orcarouter.ai/v1"
    ORCAROUTER_MODEL: str | None = None
    KIRAAI_API_KEY: str | None = None
    KIRAAI_BASE_URL: str | None = None
    KIRAAI_MODEL: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str | None = None
    AGENTROUTER_API_KEY: str | None = None
    AGENTROUTER_BASE_URL: str = "https://agentrouter.org/v1"
    AGENTROUTER_MODEL: str | None = None
    GOOGLE_API_KEY: str | None = None
    GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GOOGLE_MODEL: str | None = None
    GEMINI_API_KEY: str | None = None
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_MODEL: str | None = None
    BYTEZ_API_KEY: str | None = None
    BYTEZ_BASE_URL: str = "https://api.bytez.com/v1"
    BYTEZ_MODEL: str | None = None
    DAHL_API_KEY: str | None = None
    DAHL_BASE_URL: str | None = None
    DAHL_MODEL: str | None = None

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com/v1"
    ANTHROPIC_MODEL: str | None = None
    XKIRO_API_KEY: str | None = None
    XKIRO_BASE_URL: str = "https://api.xkiro.com/v1"
    XKIRO_MODEL: str | None = None

    GROQ_API_KEY: str | None = None
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str | None = None
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str | None = None
    MISTRAL_API_KEY: str | None = None
    MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
    MISTRAL_MODEL: str | None = None
    TOGETHER_API_KEY: str | None = None
    TOGETHER_BASE_URL: str = "https://api.together.xyz/v1"
    TOGETHER_MODEL: str | None = None
    FIREWORKS_API_KEY: str | None = None
    FIREWORKS_BASE_URL: str = "https://api.fireworks.ai/inference/v1"
    FIREWORKS_MODEL: str | None = None
    CEREBRAS_API_KEY: str | None = None
    CEREBRAS_BASE_URL: str = "https://api.cerebras.ai/v1"
    CEREBRAS_MODEL: str | None = None
    SAMBANOVA_API_KEY: str | None = None
    SAMBANOVA_BASE_URL: str = "https://api.sambanova.ai/v1"
    SAMBANOVA_MODEL: str | None = None
    DEEPINFRA_API_KEY: str | None = None
    DEEPINFRA_BASE_URL: str = "https://api.deepinfra.com/v1/openai"
    DEEPINFRA_MODEL: str | None = None
    NEBIUS_API_KEY: str | None = None
    NEBIUS_BASE_URL: str = "https://api.tokenfactory.nebius.com/v1"
    NEBIUS_MODEL: str | None = None
    NVIDIA_API_KEY: str | None = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str | None = None
    PERPLEXITY_API_KEY: str | None = None
    PERPLEXITY_BASE_URL: str = "https://api.perplexity.ai"
    PERPLEXITY_MODEL: str | None = None
    COHERE_API_KEY: str | None = None
    COHERE_BASE_URL: str = "https://api.cohere.com/compatibility/v1"
    COHERE_MODEL: str | None = None
    HUGGINGFACE_API_KEY: str | None = None
    HUGGINGFACE_BASE_URL: str = "https://router.huggingface.co/v1"
    HUGGINGFACE_MODEL: str | None = None
    NOVITA_API_KEY: str | None = None
    NOVITA_BASE_URL: str = "https://api.novita.ai/openai"
    NOVITA_MODEL: str | None = None
    SILICONFLOW_API_KEY: str | None = None
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.com/v1"
    SILICONFLOW_MODEL: str | None = None
    CHUTES_API_KEY: str | None = None
    CHUTES_BASE_URL: str = "https://llm.chutes.ai/v1"
    CHUTES_MODEL: str | None = None
    XAI_API_KEY: str | None = None
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    XAI_MODEL: str | None = None

    # Dedicated provider environment variables. Model names are intentionally
    # configurable so the router never guesses a provider-specific model id.
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com/v1"
    ANTHROPIC_MODEL: str | None = None
    XKIRO_API_KEY: str | None = None
    XKIRO_BASE_URL: str = "https://api.xkiro.com/v1"
    XKIRO_MODEL: str | None = None

    MUSIC_AUDIO_API_KEY: str | None = None
    MUSIC_AUDIO_BASE_URL: str | None = None
    MUSIC_AUDIO_MODEL: str | None = None
    MUSIC_AUDIO_PATH: str = "/audio/generations"
    MUSIC_AUDIO_MAX_SECONDS: int = 90
    MUSIC_AUDIO_FORMAT: str = "wav"
    MUSIC_AUDIO_TIMEOUT_SECONDS: int = 240
    MUSIC_GENERATION_RAHYAR_DAILY_LIMIT: int = 15
    MUSIC_GENERATION_PUBLIC_DAILY_LIMIT: int = 8

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
    CHAT_ASSISTANT_WEB_RESEARCH_ENABLED: bool = True
    CHAT_ASSISTANT_WEB_RESEARCH_RESULTS: int = 4
    CHAT_ASSISTANT_WEB_RESEARCH_MAX_CHARS: int = 22000

    KNOWLEDGE_ENABLED: bool = True
    KNOWLEDGE_GROUP_IDS: str = ""
    KNOWLEDGE_GROUP_TOPIC_ID: int = 21308
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
        model = (self.AI_MODEL or self.AI_AGENT_MODEL or "gpt-4o-mini").strip()
        host = (urlparse(self.effective_ai_base_url).hostname or "").lower()
        if host.endswith("agentrouter.org") and model.lower() in {"mimo-v2.5-free", "mimo-v2.5"}:
            fallback = (self.AI_FALLBACK_MODEL or "gpt-5.5").strip()
            return fallback or "gpt-5.5"
        return model

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
    def admin_usernames(self) -> set[str]:
        return {value.strip().lstrip("@").casefold() for value in self.ADMIN_USERNAMES.split(",") if value.strip()}

    @property
    def new_member_notification_chat_id(self) -> int:
        return self.NEW_MEMBER_NOTIFICATION_CHAT_ID or self.OWNER_ID

    @property
    def bot_deep_link_base(self) -> str | None:
        if not self.BOT_USERNAME:
            return None
        username = self.BOT_USERNAME.lstrip("@").strip()
        return f"https://t.me/{username}" if username else None

    @property
    def telegram_web_app_url(self) -> str | None:
        """Return a safe HTTPS Mini App URL or disable the button."""
        value = (self.TELEGRAM_WEB_APP_URL or "").strip()
        parsed = urlparse(value)
        return value.rstrip("/") if parsed.scheme == "https" and parsed.netloc else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
