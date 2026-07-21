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

    # LLM provider selection. "anthropic" (default) or "azure_openai".
    # All agents call through app/services/llm_gateway.py, which reads this to pick the client.
    llm_provider: str = "anthropic"

    # LLM — Anthropic (used when llm_provider == "anthropic")
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"
    llm_max_tokens: int = 16000
    # Adaptive thinking is supported on Claude 4.6+ models. Set false if you
    # point llm_model at a model that does not support extended thinking.
    llm_thinking: bool = True

    # LLM — Azure OpenAI (used when llm_provider == "azure_openai").
    # The DEPLOYMENT name is the model id passed to the API (not the base model name).
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""            # e.g. https://<resource>.openai.azure.com
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str = ""          # your deployment name, e.g. "gpt-4o"
    # Reasoning models (o1/o3/gpt-5) reject `max_tokens` and require `max_completion_tokens`.
    # Keep true (works for gpt-4o/gpt-4 too on recent API versions); set false only for an old
    # deployment/API version that predates `max_completion_tokens`.
    azure_openai_use_max_completion_tokens: bool = True

    # Database (used later for workflow state)
    database_url: str | None = None

    # Workspace
    workspace_dir: str = "app/workspace"

    # exec-sandbox MCP server (integrations/executor.py :: MCPExecutor)
    sandbox_enabled: bool = False               # connect the executor in the app lifespan
    sandbox_mcp_url: str = "http://localhost:8080/mcp"
    sandbox_mcp_transport: str = "streamable_http"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
