"""Configuration for the Interface Extraction stage (Testing Phase, Team 4).

Two kinds of config:
  * **Paths** — where this stage reads its inputs (the Source Loader Service's
    output tree under ``data/input``) and writes its artifacts (``data/``).
    Derived from the repo layout, mirroring ``source-loader-service/config.py``.
  * **LLM settings** — for A3 (the one LLM step). Populated from env vars with
    the ``TESTING_LLM_`` prefix (see root ``.env.example``); an ``.env`` is read
    if present. No key required unless a *real* A3 run happens.

Named ``ie_config`` (not ``config``) so it does not collide with the Source
Loader Service's ``config`` module, which shares ``sys.path`` in ``main.py``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ie_config.py -> interface-extraction -> testing-pipeline -> testing -> services -> <repo root>
_TESTING_DIR = Path(__file__).resolve().parents[2]
# Absolute path to the repo-root .env so config loads regardless of CWD.
_ENV_FILE = str(_TESTING_DIR.parents[1] / ".env")
DATA_DIR = _TESTING_DIR / "data"

# --- Inputs (produced by the Source Loader Service) ---
UNZIPPED_CODE_DIR = DATA_DIR / "input" / "unzipped-code"
SRS_DIR = DATA_DIR / "input" / "SRS"

# --- Outputs (this stage's artifacts) ---
CHUNKS_PATH = DATA_DIR / "Chunks" / "chunks.json"
MAPPING_TREE_PATH = DATA_DIR / "mapping-tree.json"
STRATEGY_PATH = DATA_DIR / "test-strategy.json"
# Normalized requirements are persisted too, so downstream stages (e.g. Stage B)
# consume A's parsed requirements instead of re-parsing the raw SRS.
REQUIREMENTS_PATH = DATA_DIR / "requirements.json"
# Detected tech stack, persisted so downstream stages can route generation by
# stack without re-detecting (Stage B is tech-stack agnostic).
TECH_STACK_PATH = DATA_DIR / "tech-stack.json"

# --- Source reading limits / recognized languages (A1) ---
# Extension -> language label handed to the chunker (which also infers if blank).
SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
}
MAX_SOURCE_BYTES = 1_000_000  # skip files larger than this when reading source


class LLMSettings(BaseSettings):
    """LLM config for A3. Env prefix ``TESTING_LLM_`` (e.g. TESTING_LLM_API_KEY).

    Model follows LiteLLM conventions; the verified Azure-Anthropic routing is
    ``anthropic/<model>`` + ``base_url=https://<res>.services.ai.azure.com/anthropic/``.
    """

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


llm_settings = LLMSettings()
