"""Storage abstraction for fetching source artifacts.

The loaders never touch the filesystem (or any cloud SDK) directly — they go
through a ``StorageBackend``. Today the only backend is ``LocalStorage`` (reads
from local disk); moving a source to cloud object storage later (S3 / GCS /
Azure Blob) means adding one ``StorageBackend`` subclass and one branch in
``get_storage`` — no loader logic changes.

A *root* is an opaque location string the backend understands: a directory path
for ``LocalStorage``, a bucket/prefix (e.g. ``s3://bucket/prefix``) for a future
cloud backend. A *key* is a file's path relative to that root (posix-style).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from exceptions import SourceLoadError


class StorageBackend(ABC):
    """Read-only source of artifact files, location-agnostic."""

    @abstractmethod
    def exists(self, root: str) -> bool:
        """Whether the root location is reachable."""

    @abstractmethod
    def list_files(
        self,
        root: str,
        *,
        suffix: str | None = None,
        ignore_names: Iterable[str] = (),
    ) -> list[str]:
        """Keys of all files under ``root`` (recursive), relative to ``root``.

        Args:
            suffix: if given, only keys whose filename ends with it.
            ignore_names: filenames to skip entirely (e.g. ``README.md``).
        """

    @abstractmethod
    def read_bytes(self, root: str, key: str) -> bytes:
        """Read one file's raw bytes."""


class LocalStorage(StorageBackend):
    """Reads artifacts from the local filesystem."""

    def exists(self, root: str) -> bool:
        return Path(root).is_dir()

    def list_files(
        self,
        root: str,
        *,
        suffix: str | None = None,
        ignore_names: Iterable[str] = (),
    ) -> list[str]:
        base = Path(root)
        ignore = set(ignore_names)
        keys: list[str] = []
        for path in sorted(base.rglob("*")):
            if path.is_dir() or path.name in ignore:
                continue
            if suffix is not None and not path.name.endswith(suffix):
                continue
            keys.append(path.relative_to(base).as_posix())
        return keys

    def read_bytes(self, root: str, key: str) -> bytes:
        return (Path(root) / key).read_bytes()


def get_storage(backend: str) -> StorageBackend:
    """Return the configured storage backend.

    Extend here for cloud: ``if backend == "s3": return S3Storage(...)``.
    """
    if backend == "local":
        return LocalStorage()
    raise SourceLoadError(
        "unsupported_storage", f"Unknown storage backend: {backend!r}"
    )
