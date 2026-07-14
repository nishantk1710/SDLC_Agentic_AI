"""Configuration for the Source Loader Service.

Paths default to the repo layout but are overridable via environment variables
(prefix ``SOURCE_LOADER_``) so the same module runs in local dev, tests, and the
containerized testing phase. Safety limits guard against zip bombs and runaway
archives; tune them per the sidecar's resource caps once those are signed off
(reference §3, §12).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> source-loader-service -> testing -> services -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_ZIP_SOURCE_DIR = REPO_ROOT / "contracts" / "shared" / "zipped_code"
_DEFAULT_UNZIP_DEST_DIR = (
    REPO_ROOT / "services" / "testing" / "data" / "input" / "unzipped-code"
)


class Settings(BaseSettings):
    """Runtime configuration, populated from env vars with sensible defaults."""

    model_config = SettingsConfigDict(
        env_prefix="SOURCE_LOADER_", env_file=".env", extra="ignore"
    )

    # --- Paths ---
    zip_source_dir: Path = Field(
        default=_DEFAULT_ZIP_SOURCE_DIR,
        description="Fixed directory the zip artifact is fetched from.",
    )
    unzip_dest_dir: Path = Field(
        default=_DEFAULT_UNZIP_DEST_DIR,
        description="Where extracted source code is written.",
    )
    srs_source_dir: Path = Field(
        default=REPO_ROOT / "contracts" / "shared" / "SRS",
        description="Fixed directory the SRS (requirements) artifact is fetched from.",
    )
    srs_dest_dir: Path = Field(
        default=REPO_ROOT / "services" / "testing" / "data" / "input" / "SRS",
        description="Where the SRS artifact is copied to (any file type).",
    )
    design_source_dir: Path = Field(
        default=REPO_ROOT / "contracts" / "shared" / "design-artifact",
        description="Fixed directory the design artifact is fetched from.",
    )
    design_dest_dir: Path = Field(
        default=REPO_ROOT
        / "services"
        / "testing"
        / "data"
        / "input"
        / "design-artifact",
        description="Where the design artifact is copied to (any file type).",
    )

    # --- Safety limits (zip-bomb / abuse guards) ---
    max_file_bytes: int = Field(
        default=50 * 1024 * 1024, description="Max uncompressed size per entry."
    )
    max_total_bytes: int = Field(
        default=500 * 1024 * 1024, description="Max uncompressed size for the archive."
    )
    max_files: int = Field(
        default=10_000, description="Max number of entries in the archive."
    )
    max_compression_ratio: int = Field(
        default=100,
        description="Reject an entry whose uncompressed/compressed ratio exceeds this.",
    )

    # --- Cleanliness ---
    # Extension/segment patterns skipped so downstream chunking sees clean source.
    skip_suffixes: tuple[str, ...] = (".pyc", ".pyo", ".DS_Store")
    skip_dir_segments: tuple[str, ...] = ("__pycache__", ".git")


settings = Settings()
