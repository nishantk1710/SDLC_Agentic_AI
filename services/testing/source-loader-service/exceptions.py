"""Failure types for the Source Loader Service.

A ``SourceLoadError`` is the source-loading failure path called out in the
implementation reference (§9): it must surface as an ``ERROR`` verdict rather
than crashing the pipeline. Each error carries a machine-readable ``code`` so
callers can distinguish *why* loading failed.
"""

from __future__ import annotations


class SourceLoadError(Exception):
    """Raised when the zip artifact cannot be safely loaded.

    Attributes:
        code: short, stable identifier for the failure category, e.g.
            ``"no_zip_found"``, ``"not_a_zip"``, ``"zip_slip"``,
            ``"entry_too_large"``, ``"archive_too_large"``, ``"too_many_files"``,
            ``"symlink_rejected"``, ``"bad_zip"``.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
