"""Safe zip extraction — the heart of the Source Loader Service.

Strategy (option 2, per design discussion): iterate ``ZipFile.infolist()`` and
validate every entry *before* writing it, rather than trusting ``extractall``.
Guards, in order, against:

  * **Zip-slip / path traversal** — the resolved target must stay inside the
    destination root (absolute paths and ``..`` segments are rejected).
  * **Symlinks** — link entries are refused outright (they can point outside the
    tree even after path checks pass).
  * **Zip bombs** — per-entry size, whole-archive size, entry count, and per-entry
    compression-ratio caps.

Junk (``__pycache__``, ``*.pyc``, ``.git`` …) is skipped so the downstream
chunking stage sees clean source. Failures raise ``SourceLoadError`` — the
caller maps that to an ``ERROR`` verdict.
"""

from __future__ import annotations

import logging
import shutil
import stat
import zipfile
from pathlib import Path

from config import Settings, settings
from exceptions import SourceLoadError
from fsutil import reset_dir
from models import ExtractedFile, LoadResult

logger = logging.getLogger(__name__)

# High 16 bits of external_attr hold the Unix mode; this masks the file type.
_S_IFMT_SHIFT = 16


def _find_zip(source_dir: Path) -> Path:
    """Locate the single ``*.zip`` in the fixed source directory."""
    if not source_dir.is_dir():
        raise SourceLoadError(
            "no_zip_found", f"Zip source directory does not exist: {source_dir}"
        )
    zips = sorted(source_dir.glob("*.zip"))
    if not zips:
        raise SourceLoadError("no_zip_found", f"No .zip file found in {source_dir}")
    if len(zips) > 1:
        logger.warning(
            "Multiple zips in %s; using first: %s", source_dir, zips[0].name
        )
    return zips[0]


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> _S_IFMT_SHIFT
    return stat.S_ISLNK(mode)


def _is_junk(name: str, cfg: Settings) -> bool:
    parts = Path(name).parts
    if any(seg in cfg.skip_dir_segments for seg in parts):
        return True
    return name.endswith(cfg.skip_suffixes)


def _safe_target(dest_root: Path, name: str) -> Path:
    """Resolve an entry name under ``dest_root`` or reject it as zip-slip."""
    target = (dest_root / name).resolve()
    if target != dest_root and dest_root not in target.parents:
        raise SourceLoadError(
            "zip_slip", f"Entry escapes destination directory: {name!r}"
        )
    return target


def load_source(
    zip_path: Path | None = None, cfg: Settings = settings
) -> LoadResult:
    """Fetch the zip from the fixed path and extract it safely.

    Args:
        zip_path: explicit zip to load; if ``None``, the single zip in
            ``cfg.zip_source_dir`` is used.
        cfg: settings (paths + limits); defaults to the module-level singleton.

    Returns:
        A ``LoadResult`` with ``status="OK"`` and a manifest of written files.

    Raises:
        SourceLoadError: on any validation or extraction failure.
    """
    zip_path = zip_path or _find_zip(cfg.zip_source_dir)

    if not zip_path.is_file():
        raise SourceLoadError("no_zip_found", f"Zip file not found: {zip_path}")
    if not zipfile.is_zipfile(zip_path):
        raise SourceLoadError("not_a_zip", f"Not a valid zip archive: {zip_path}")

    dest_root = cfg.unzip_dest_dir.resolve()
    reset_dir(dest_root)

    extracted: list[ExtractedFile] = []
    skipped: list[str] = []
    total_bytes = 0

    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            if len(infos) > cfg.max_files:
                raise SourceLoadError(
                    "too_many_files",
                    f"Archive has {len(infos)} entries (limit {cfg.max_files}).",
                )

            for info in infos:
                name = info.filename

                if _is_symlink(info):
                    raise SourceLoadError(
                        "symlink_rejected", f"Symlink entry not allowed: {name!r}"
                    )

                target = _safe_target(dest_root, name)

                # Directory entry: preserve structure, nothing to size-check.
                if name.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                if _is_junk(name, cfg):
                    skipped.append(name)
                    continue

                if info.file_size > cfg.max_file_bytes:
                    raise SourceLoadError(
                        "entry_too_large",
                        f"{name!r} is {info.file_size} bytes "
                        f"(limit {cfg.max_file_bytes}).",
                    )

                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > cfg.max_compression_ratio:
                        raise SourceLoadError(
                            "entry_too_large",
                            f"{name!r} compression ratio {ratio:.0f}:1 exceeds "
                            f"limit {cfg.max_compression_ratio}:1 (possible zip bomb).",
                        )

                total_bytes += info.file_size
                if total_bytes > cfg.max_total_bytes:
                    raise SourceLoadError(
                        "archive_too_large",
                        f"Uncompressed size exceeds {cfg.max_total_bytes} bytes.",
                    )

                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                extracted.append(
                    ExtractedFile(
                        path=str(target.relative_to(dest_root).as_posix()),
                        size_bytes=info.file_size,
                    )
                )
    except zipfile.BadZipFile as exc:
        raise SourceLoadError("bad_zip", f"Corrupt zip archive: {exc}") from exc

    logger.info(
        "Loaded %s: %d files, %d bytes (%d skipped) -> %s",
        zip_path.name,
        len(extracted),
        total_bytes,
        len(skipped),
        dest_root,
    )

    return LoadResult(
        status="OK",
        zip_name=zip_path.name,
        dest_dir=str(dest_root),
        file_count=len(extracted),
        total_bytes=total_bytes,
        files=extracted,
        skipped=skipped,
    )
