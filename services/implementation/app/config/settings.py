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

    # LLM (Claude / Anthropic) — public API or a Foundry-style proxy.
    # If the Foundry vars are set they take precedence and calls are routed to
    # ANTHROPIC_FOUNDRY_BASE_URL; otherwise the public Anthropic API is used.
    anthropic_api_key: str = ""
    anthropic_foundry_api_key: str = ""
    anthropic_foundry_base_url: str = ""
    llm_model: str = "claude-opus-4-8"
    llm_max_tokens: int = 16000
    # Adaptive thinking is supported on Claude 4.6+ models. Set false if you
    # point llm_model at a model that does not support extended thinking.
    llm_thinking: bool = True

    # Database (used later for workflow state)
    database_url: str | None = None

    # Workspace
    workspace_dir: str = "app/workspace"

    # exec-sandbox MCP server (integrations/executor.py :: MCPExecutor)
    sandbox_enabled: bool = False               # connect the executor in the app lifespan
    sandbox_mcp_url: str = "http://localhost:8080/mcp"
    sandbox_mcp_transport: str = "streamable_http"

    # Code Review: clones the generated PUBLIC repo into an EPHEMERAL sandbox, runs static
    # analysis (ruff/eslint + sonar-scanner) inside it, tears it down, then writes a Markdown
    # report. No code is executed (Testing does that); no repo token is needed (public repos).
    review_sandbox_image: str = "sdlc-review-sandbox:latest"  # image w/ git+ruff+node/eslint+sonar-scanner
    review_sandbox_timeout: float = 900.0                     # hard cap on the whole session (s)
    reports_dir: str = "reports"                              # where <project>-<run>.md reports land
    # Git working model: all phases work on this branch; it is merged -> main only after the
    # Security scan passes (final step).
    working_branch: str = "dev"

    # SonarQube static analysis (integrations/sonarqube.py). OFF by default; when disabled the
    # review runs on ruff/eslint + the LLM alone. NOTE two URLs for the same server:
    #   * sonarqube_scanner_url — used by sonar-scanner INSIDE the sandbox container (upload)
    #   * sonarqube_url         — used by the agent ON THE HOST to read issues back
    sonarqube_enabled: bool = False
    sonarqube_url: str = "http://localhost:9000"                 # host-side read (published port)
    sonarqube_scanner_url: str = "http://host.docker.internal:9000"  # sandbox-side upload
    sonarqube_token: str = ""                   # user/analysis token (Bearer auth)
    sonarqube_project_key: str = ""             # component key to scan + pull issues for
    sonarqube_timeout: float = 30.0             # HTTP timeout in seconds


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
