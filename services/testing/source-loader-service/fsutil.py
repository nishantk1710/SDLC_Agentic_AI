"""Filesystem helpers shared by the loaders."""

from __future__ import annotations

import shutil
from pathlib import Path

# Structure placeholders that must survive a reset so empty dirs stay tracked.
KEEP_NAMES = frozenset({".gitkeep"})


def reset_dir(path: Path) -> None:
    """Wipe a directory's contents so each run starts clean, keeping the dir
    itself and any structure placeholders (``.gitkeep``)."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return
    for child in path.iterdir():
        if child.name in KEEP_NAMES:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
