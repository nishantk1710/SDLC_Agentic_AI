"""Pass-through artifact loading (SRS and the design artifact).

Unlike the source code (which arrives zipped and is extracted), the SRS and
design artifacts are copied **verbatim** from their contract handoff locations
into the testing phase's input tree — any file type, no parsing. The reference
design calls these "structured data that passes through alongside the source
code" (§1); this loader is just the fetch-and-place step.

Reads go through a ``StorageBackend`` (local disk today, cloud later). The
contract's own bookkeeping files (``README.md`` schema doc, ``.gitkeep``) live
alongside the payload in the source and are skipped via ``cfg.ignore_names``.
Structure placeholders in the destination (``.gitkeep``) are preserved.
"""

from __future__ import annotations

import logging

from config import Settings, settings
from exceptions import SourceLoadError
from fsutil import reset_dir
from models import ArtifactLoadResult, ExtractedFile
from storage import get_storage

logger = logging.getLogger(__name__)


def _copy_artifact(
    name: str, source: str, dest_dir, cfg: Settings
) -> ArtifactLoadResult:
    """Copy every payload file under ``source`` into ``dest_dir``.

    Args:
        name: label for the artifact (e.g. ``"SRS"``), used in logs/result.
        source: contract handoff location the artifact is fetched from.
        dest_dir: local directory the artifact is copied to.
        cfg: settings (storage backend + ignore list).

    Raises:
        SourceLoadError: if the source location is missing.
    """
    store = get_storage(cfg.storage_backend)
    if not store.exists(source):
        raise SourceLoadError(
            "no_artifact_dir", f"{name} source location does not exist: {source}"
        )

    dest_root = dest_dir.resolve()
    reset_dir(dest_root)

    copied: list[ExtractedFile] = []
    total_bytes = 0

    for key in store.list_files(source, ignore_names=cfg.ignore_names):
        data = store.read_bytes(source, key)
        target = dest_root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        total_bytes += len(data)
        copied.append(ExtractedFile(path=key, size_bytes=len(data)))

    if not copied:
        logger.warning("%s source location is empty: %s", name, source)

    logger.info(
        "Loaded %s: %d files, %d bytes -> %s",
        name,
        len(copied),
        total_bytes,
        dest_root,
    )

    return ArtifactLoadResult(
        status="OK",
        artifact=name,
        source_dir=source,
        dest_dir=str(dest_root),
        file_count=len(copied),
        total_bytes=total_bytes,
        files=copied,
    )


def load_srs(cfg: Settings = settings) -> ArtifactLoadResult:
    """Pull the SRS (requirements) artifact from its contract handoff location
    (``requirements-to-design``) into the input tree. Any file type, verbatim."""
    return _copy_artifact("SRS", cfg.srs_source, cfg.srs_dest_dir, cfg)


def load_design(cfg: Settings = settings) -> ArtifactLoadResult:
    """Pull the design artifact from its contract handoff location
    (``design-to-implementation``) into the input tree. Any file type, verbatim."""
    return _copy_artifact("design", cfg.design_source, cfg.design_dest_dir, cfg)
