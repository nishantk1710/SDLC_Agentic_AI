"""Configuration for the Test-Case Derivation stage (Stage B, Testing Phase).

Reads Stage A's persisted artifacts from ``data/`` and writes ``test-cases.json``
there. LLM settings share the ``TESTING_LLM_`` env prefix with Stage A, so one
``.env`` configures both. MCP settings use ``TESTING_MCP_`` and are optional —
when unset, the router uses the direct-LLM path (see ``mcp_adapter.py``).

Named ``tcd_config`` (not ``config``) so it never collides with the Source
Loader Service's ``config`` or Stage A's ``ie_config`` on the shared ``sys.path``.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# tcd_config.py -> test-case-derivation -> testing-pipeline -> testing -> services -> <repo root>
_TESTING_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _TESTING_DIR.parents[1]
# Absolute path to the repo-root .env so config loads regardless of the process
# working directory (stages run from their own dirs).
_ENV_FILE = str(_REPO_ROOT / ".env")
DATA_DIR = _TESTING_DIR / "data"

# --- Inputs (Stage A artifacts) ---
MAPPING_TREE_PATH = DATA_DIR / "mapping-tree.json"
STRATEGY_PATH = DATA_DIR / "test-strategy.json"
REQUIREMENTS_PATH = DATA_DIR / "requirements.json"
TECH_STACK_PATH = DATA_DIR / "tech-stack.json"

# --- Output (this stage's artifact) ---
TEST_CASES_PATH = DATA_DIR / "test-cases.json"

# --- Cache (optimization, not a determinism guarantee — reference §7.5) ---
CACHE_DIR = DATA_DIR / ".cache" / "test-cases"
CACHE_ENABLED = os.getenv("TESTING_TCD_CACHE", "1") not in ("0", "false", "False")

# Functional case types for the POC (reference §7.4).
CASE_TYPES = ("happy_path", "boundary", "invalid_input", "error_handling")


class LLMSettings(BaseSettings):
    """LLM config for the direct-LLM planner. Shares Stage A's ``TESTING_LLM_``."""

    model_config = SettingsConfigDict(
        env_prefix="TESTING_LLM_", env_file=_ENV_FILE, extra="ignore"
    )

    model: str = "anthropic/claude-sonnet-4-6"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.0
    timeout: float = 60.0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


class MCPSettings(BaseSettings):
    """ZenseAI MCP tool config. Unset in the POC -> router falls back to LLM."""

    model_config = SettingsConfigDict(
        env_prefix="TESTING_MCP_", env_file=_ENV_FILE, extra="ignore"
    )

    url: str | None = None          # MCP endpoint; unset => MCP unavailable
    api_key: str | None = None      # passed to the tool as its `bearer_token` arg
    api_id: int | None = None       # passed to the tool as its `api_id` arg (aibuddy credential selector)

    @field_validator("url", "api_key", "api_id", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        # An empty env value (e.g. TESTING_MCP_API_ID=) must not fail int parsing.
        return None if isinstance(v, str) and v.strip() == "" else v
    timeout: float = 20.0
    # The ZenseAI tool function name (see blueprint §4.1). Configurable in case a
    # deployment renames it.
    tool_name: str = "call_python_test_case_generation_genie"
    # Languages the MCP genie can serve; other stacks use the LLM fallback.
    # Comma-separated env value is coerced to a tuple.
    supported_languages: tuple[str, ...] = ("python",)

    @property
    def is_available(self) -> bool:
        return bool(self.url)


llm_settings = LLMSettings()
mcp_settings = MCPSettings()
