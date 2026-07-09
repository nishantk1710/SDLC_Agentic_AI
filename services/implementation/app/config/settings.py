"""Centralized configuration loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service
    app_name: str = "implementation-service"
    log_level: str = "INFO"

    # LLM (Claude / Anthropic)
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"
    llm_max_tokens: int = 16000

    # Database (used later for workflow state)
    database_url: str | None = None

    # Workspace
    workspace_dir: str = "app/workspace"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
