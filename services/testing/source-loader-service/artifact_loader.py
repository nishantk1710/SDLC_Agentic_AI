"""Pass-through artifact loading (SRS, and later the design artifact).

Unlike the source code (which arrives zipped and is extracted), the SRS and
design artifacts are copied **verbatim** from ``contracts/shared`` into the
testing phase's input tree — any file type, no parsing. The reference design
calls these "structured data that passes through alongside the source code"
(§1); this loader is just the fetch-and-place step.

Structure placeholders (``.gitkeep``) are neither copied nor removed.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from config import Settings, settings
from exceptions import SourceLoadError
from fsutil import KEEP_NAMES, reset_dir
from models import ArtifactLoadResult, ExtractedFile

logger = logging.getLogger(__name__)


def _copy_artifact(
    name: str, source_dir: Path, dest_dir: Path
) -> ArtifactLoadResult:
    """Copy every file under ``source_dir`` into ``dest_dir``, recursively.

    Args:
        name: label for the artifact (e.g. ``"SRS"``), used in logs/result.
        source_dir: fixed directory the artifact is fetched from.
        dest_dir: where the artifact is copied to.

    Raises:
        SourceLoadError: if the source directory is missing.
    """
    if not source_dir.is_dir():
        raise SourceLoadError(
            "no_artifact_dir", f"{name} source directory does not exist: {source_dir}"
        )

    dest_root = dest_dir.resolve()
    reset_dir(dest_root)

    copied: list[ExtractedFile] = []
    total_bytes = 0

    for src in sorted(source_dir.rglob("*")):
        if src.is_dir() or src.name in KEEP_NAMES:
            continue
        rel = src.relative_to(source_dir)
        target = dest_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        size = src.stat().st_size
        total_bytes += size
        copied.append(ExtractedFile(path=rel.as_posix(), size_bytes=size))

    if not copied:
        logger.warning("%s source directory is empty: %s", name, source_dir)

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
        source_dir=str(source_dir),
        dest_dir=str(dest_root),
        file_count=len(copied),
        total_bytes=total_bytes,
        files=copied,
    )


def load_srs(cfg: Settings = settings) -> ArtifactLoadResult:
    """Pull the SRS (requirements) artifact from ``contracts/shared/SRS`` into
    the testing phase's input tree. Any file type is copied verbatim."""
    return _copy_artifact("SRS", cfg.srs_source_dir, cfg.srs_dest_dir)


def load_design(cfg: Settings = settings) -> ArtifactLoadResult:
    """Pull the design artifact from ``contracts/shared/design-artifact`` into
    the testing phase's input tree. Any file type is copied verbatim."""
    return _copy_artifact("design", cfg.design_source_dir, cfg.design_dest_dir)
