"""Safe zip extraction — the heart of the Source Loader Service.

The zip is fetched through a ``StorageBackend`` (local disk today, cloud object
storage later) as raw bytes, then extracted in memory. Strategy (option 2, per
design discussion): iterate ``ZipFile.infolist()`` and validate every entry
*before* writing it, rather than trusting ``extractall``. Guards, in order,
against:

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

import io
import logging
import shutil
import stat
import zipfile
from pathlib import Path

from config import Settings, settings
from exceptions import SourceLoadError
from fsutil import reset_dir
from models import ExtractedFile, LoadResult
from storage import StorageBackend, get_storage

logger = logging.getLogger(__name__)

# High 16 bits of external_attr hold the Unix mode; this masks the file type.
_S_IFMT_SHIFT = 16


def _find_zip_key(store: StorageBackend, root: str, cfg: Settings) -> str:
    """Locate the single ``*.zip`` under the source location."""
    if not store.exists(root):
        raise SourceLoadError(
            "no_zip_found", f"Zip source location does not exist: {root}"
        )
    zip_keys = store.list_files(root, suffix=".zip", ignore_names=cfg.ignore_names)
    if not zip_keys:
        raise SourceLoadError("no_zip_found", f"No .zip file found in {root}")
    if len(zip_keys) > 1:
        logger.warning("Multiple zips in %s; using first: %s", root, zip_keys[0])
    return zip_keys[0]


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


def load_source(cfg: Settings = settings) -> LoadResult:
    """Fetch the zipped source code from its contract handoff location and
    extract it safely into the local input tree.

    Args:
        cfg: settings (sources, destinations, limits); defaults to the
            module-level singleton.

    Returns:
        A ``LoadResult`` with ``status="OK"`` and a manifest of written files.

    Raises:
        SourceLoadError: on any validation or extraction failure.
    """
    store = get_storage(cfg.storage_backend)
    zip_key = _find_zip_key(store, cfg.zip_source, cfg)
    data = store.read_bytes(cfg.zip_source, zip_key)
    zip_name = Path(zip_key).name

    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise SourceLoadError("not_a_zip", f"Not a valid zip archive: {zip_key}")

    dest_root = cfg.unzip_dest_dir.resolve()
    reset_dir(dest_root)

    extracted: list[ExtractedFile] = []
    skipped: list[str] = []
    total_bytes = 0

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
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
        zip_name,
        len(extracted),
        total_bytes,
        len(skipped),
        dest_root,
    )

    return LoadResult(
        status="OK",
        zip_name=zip_name,
        dest_dir=str(dest_root),
        file_count=len(extracted),
        total_bytes=total_bytes,
        files=extracted,
        skipped=skipped,
    )
