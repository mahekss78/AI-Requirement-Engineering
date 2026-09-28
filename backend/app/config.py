"""
app/config.py
=============
Central configuration manager for the AREA platform.

Uses Pydantic's BaseSettings to read environment variables from the .env file
at startup. Every module that needs a config value imports the `settings`
singleton from this file rather than calling os.environ directly.

This ensures:
- Type safety on all config values (Pydantic validates and coerces types).
- A single point of failure: if a required variable is missing, the app
  fails at startup with a clear error rather than at runtime.
- Easy overriding in tests via environment variable injection.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application-wide settings loaded from .env.
    All fields are typed so Pydantic will raise a ValidationError on startup
    if a required variable is missing or of the wrong type.
    """

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/area_db"

    # ------------------------------------------------------------------ #
    # OpenAI / LLM
    # ------------------------------------------------------------------ #
    OPENAI_API_KEY: str = "sk-placeholder"

    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 4096

    # ------------------------------------------------------------------ #
    # ChromaDB (Local Vector Store)
    # ------------------------------------------------------------------ #
    CHROMA_DB_PATH: str = "./chroma_data"

    # ------------------------------------------------------------------ #
    # RAG Embedding Model (local sentence-transformers, no API needed)
    # ------------------------------------------------------------------ #
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ------------------------------------------------------------------ #
    # Jira Integration (optional for MVP; features degrade gracefully)
    # ------------------------------------------------------------------ #
    JIRA_DOMAIN: str = ""
    JIRA_EMAIL: str = ""
    JIRA_API_TOKEN: str = ""
    JIRA_PROJECT_KEY: str = "XYZ"

    # ------------------------------------------------------------------ #
    # SMTP / Notifications (optional for MVP)
    # ------------------------------------------------------------------ #
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # ------------------------------------------------------------------ #
    # OAuth 2.0 Provider Settings
    # ------------------------------------------------------------------ #
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/oauth/google/callback"

    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_REDIRECT_URI: str = "http://localhost:8000/api/auth/oauth/microsoft/callback"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/api/auth/oauth/github/callback"

    # ------------------------------------------------------------------ #
    # Pydantic-Settings model configuration
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=(".env.example", "../.env.example", ".env", "../.env"),   # .env overrides .env.example
        env_file_encoding="utf-8",
        case_sensitive=True,      # Match variable names exactly
        extra="ignore",           # Silently ignore unknown env vars
    )

    @property
    def is_jira_configured(self) -> bool:
        """True when all three Jira credentials are present."""
        return bool(self.JIRA_DOMAIN and self.JIRA_EMAIL and self.JIRA_API_TOKEN)

    @property
    def is_google_oauth_configured(self) -> bool:
        """True when Google OAuth credentials are present."""
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def is_smtp_configured(self) -> bool:
        """True when SMTP credentials are present."""
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)


@lru_cache
def get_settings() -> Settings:
    """
    Returns the cached Settings singleton.
    Using @lru_cache means the .env file is only parsed once, regardless
    of how many modules call get_settings().
    """
    return Settings()


# Module-level singleton for convenient import:
#   from app.config import settings
settings = get_settings()
