"""A1 fallback chunker — for languages without a registered symbol parser.

The reference doc calls for ``RecursiveCharacterTextSplitter.from_language``
here. To keep the POC dependency-free we implement a simple character-window
splitter with overlap. It is deliberately coarse: the resulting chunks are
NOT symbol-aligned, so the A2 mapping tree over them will be fuzzy. That is
the expected trade-off until a real tree-sitter grammar is registered for the
language in ``codebase_chunker._PARSERS``.

The name "llm_fallback" is kept for continuity with the reference layout; an
actual LLM-based structural extraction can be slotted in behind this same
function signature later without changing callers.
"""

from __future__ import annotations

from typing import Dict, List

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

Chunk = Dict[str, object]


def fallback_chunk_file(
    path: str,
    content: str,
    language: str = "unknown",
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[Chunk]:
    """Coarse, symbol-agnostic chunks so no file is dropped."""
    content = content or ""
    if not content.strip():
        return []

    chunks: List[Chunk] = []
    step = max(1, chunk_size - overlap)
    idx = 0
    for start in range(0, len(content), step):
        window = content[start : start + chunk_size]
        if not window.strip():
            continue
        # Approximate line numbers for the window.
        start_line = content.count("\n", 0, start) + 1
        end_line = start_line + window.count("\n")
        chunks.append(
            {
                "symbol_id": f"{path}::chunk_{idx}",
                "filename": path,
                "language": language,
                "symbol_type": "chunk",
                "signature": "",
                "content": window,
                "start_line": start_line,
                "end_line": end_line,
                "calls": [],  # not extractable without a real parser
                "is_test": False,
            }
        )
        idx += 1
        if start + chunk_size >= len(content):
            break
    return chunks
