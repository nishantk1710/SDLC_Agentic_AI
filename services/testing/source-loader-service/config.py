"""Configuration for the Source Loader Service.

Defaults follow the repo layout but are overridable via environment variables
(prefix ``SOURCE_LOADER_``) so the same module runs in local dev, tests, and the
containerized testing phase.

Sources are the contract *handoff* folders (each upstream phase drops its output
where the next phase reads it). They are expressed as opaque location strings so
the same config works whether the backend is local disk or, later, cloud object
storage — see ``storage.py`` and ``storage_backend`` below. Destinations are
always local (the phase's working input tree).

Safety limits guard against zip bombs and runaway archives; tune them per the
sidecar's resource caps once those are signed off (reference §3, §12).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> source-loader-service -> testing -> services -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]

_CONTRACTS = REPO_ROOT / "contracts"
_INPUT = REPO_ROOT / "services" / "testing" / "data" / "input"


class Settings(BaseSettings):
    """Runtime configuration, populated from env vars with sensible defaults."""

    model_config = SettingsConfigDict(
        env_prefix="SOURCE_LOADER_", env_file=".env", extra="ignore"
    )

    # --- Storage backend ---
    # Which StorageBackend fetches sources: "local" today; "s3"/"gcs"/... later.
    storage_backend: str = Field(default="local")

    # --- Sources (contract handoff folders; opaque location strings) ---
    zip_source: str = Field(
        default=str(_CONTRACTS / "implementation-to-testing"),
        description="Where the zipped source code is fetched from (impl -> testing).",
    )
    srs_source: str = Field(
        default=str(_CONTRACTS / "requirements-to-design"),
        description="Where the SRS is fetched from (requirements -> design).",
    )
    design_source: str = Field(
        default=str(_CONTRACTS / "design-to-implementation"),
        description="Where the design artifact is fetched from (design -> impl).",
    )

    # --- Destinations (always local working tree) ---
    unzip_dest_dir: Path = Field(
        default=_INPUT / "unzipped-code",
        description="Where extracted source code is written.",
    )
    srs_dest_dir: Path = Field(
        default=_INPUT / "SRS",
        description="Where the SRS artifact is copied to (any file type).",
    )
    design_dest_dir: Path = Field(
        default=_INPUT / "design-artifact",
        description="Where the design artifact is copied to (any file type).",
    )

    # --- Non-artifact files present in a source that must never be loaded ---
    # e.g. the contract's own README.md schema doc sits alongside the payload.
    ignore_names: tuple[str, ...] = ("README.md", ".gitkeep")

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
