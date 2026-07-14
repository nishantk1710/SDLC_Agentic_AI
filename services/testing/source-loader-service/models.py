"""Response schemas for the Source Loader Service.

These stay intentionally small for now; once ``contracts/shared`` freezes the
``AgentResponse`` envelope, ``LoadResult`` should be wrapped by / aligned to it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedFile(BaseModel):
    """One file written to the destination tree."""

    path: str = Field(description="Path relative to the unzip destination root.")
    size_bytes: int


class LoadResult(BaseModel):
    """Outcome of a source-loading run."""

    status: Literal["OK", "ERROR"]
    zip_name: str | None = None
    dest_dir: str | None = None
    file_count: int = 0
    total_bytes: int = 0
    files: list[ExtractedFile] = Field(default_factory=list)
    skipped: list[str] = Field(
        default_factory=list, description="Entries skipped as junk (pyc, __pycache__, …)."
    )
    error_code: str | None = None
    error_message: str | None = None


class ArtifactLoadResult(BaseModel):
    """Outcome of copying a pass-through artifact (e.g. SRS, design) into the
    testing phase's input tree. The artifact may be any file type; it is copied
    verbatim, not parsed."""

    status: Literal["OK", "ERROR"]
    artifact: str = Field(description="Which artifact was loaded, e.g. 'SRS'.")
    source_dir: str | None = None
    dest_dir: str | None = None
    file_count: int = 0
    total_bytes: int = 0
    files: list[ExtractedFile] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
