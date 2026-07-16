"""
tech_stack.py — resolves the project's tech stack for routing Step C's
code generation (which codegen/<runtime>.py handles this run).

Tech stack is project-level, not per-test-case. Two sources are checked,
in priority order:

1. services/testing/data/Chunks/chunks.json (Step A's tree-sitter output)
   -- parsed directly from the real source files, so it's ground truth.
   Preferred over (2) because a design doc can describe an aspirational or
   just-plain-wrong stack: confirmed on real QuickBite data, where
   contracts/design-to-implementation/extracted_requirements.json's
   tech_stack narrative claims a "MERN stack" (Node/Express) backend, but
   the actual chunked source (quickbite/backend/app/main.py) is Python
   (FastAPI-style). Trusting the narrative text there would have generated
   JavaScript tests against Python code.
2. contracts/design-to-implementation/extracted_requirements.json's
   tech_stack field -- only consulted if Chunks doesn't exist/parse. Its
   tech_stack field is prose (a list of {section, text} entries from the
   SRS's "Technology Stack" section, not a simple string), so resolving it
   means keyword-matching within the text, not just reading a field. Known
   to be unreliable relative to the real code (see above) -- kept only as
   a fallback for when Chunks hasn't been produced yet.

Neither source existing yet is the current default in a fresh repo, so
this resolver is defensive throughout: falls back to "python" and logs a
clear warning rather than failing the whole run.
"""

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TECH_STACK = "python"
DESIGN_TO_IMPLEMENTATION_DIR = Path("contracts/design-to-implementation")
CHUNKS_DIR = Path("services/testing/data/Chunks")

_LANGUAGE_TO_STACK = {
    "python": "python",
    "javascript": "node",
    "typescript": "node",
}

# Checked in order -- most specific framework name first, so "express.js"
# matches before a bare "node.js" mention would.
_TEXT_KEYWORDS = [
    ("express.js", "node"),
    ("express", "node"),
    ("node.js", "node"),
    ("nodejs", "node"),
    ("fastapi", "python"),
    ("django", "python"),
    ("flask", "python"),
]


def resolve_tech_stack(
    contracts_dir: Path = DESIGN_TO_IMPLEMENTATION_DIR,
    chunks_dir: Path = CHUNKS_DIR,
) -> str:
    """Resolve the project's backend tech stack. Chunks (real source, via
    tree-sitter) takes priority over the extracted-requirements document's
    narrative tech_stack text, since the latter can describe a stack that
    doesn't match what was actually implemented. Falls back to
    DEFAULT_TECH_STACK if neither source resolves anything."""
    from_chunks = _resolve_from_chunks(chunks_dir)
    if from_chunks is not None:
        logger.info("tech_stack=%r resolved from %s", from_chunks, chunks_dir)
        return from_chunks

    from_narrative = _resolve_from_extracted_requirements(contracts_dir)
    if from_narrative is not None:
        logger.info(
            "tech_stack=%r resolved from extracted-requirements document under %s",
            from_narrative, contracts_dir,
        )
        return from_narrative

    logger.warning(
        "could not resolve tech_stack from %s or %s; defaulting to %r",
        chunks_dir, contracts_dir, DEFAULT_TECH_STACK,
    )
    return DEFAULT_TECH_STACK


def _resolve_from_chunks(chunks_dir: Path) -> Optional[str]:
    """Looks for *.json chunk files under chunks_dir, filters to backend
    chunks (filename contains "backend", falling back to is_endpoint=True
    chunks if no such filenames exist), and returns the most common
    language among them, mapped to a routing key."""
    if not chunks_dir.exists():
        return None

    chunks = _load_chunks(chunks_dir)
    if not chunks:
        return None

    backend_chunks = [c for c in chunks if "backend" in str(c.get("filename", "")).lower()]
    if not backend_chunks:
        backend_chunks = [c for c in chunks if c.get("is_endpoint")]
    if not backend_chunks:
        backend_chunks = chunks  # last resort: everything in the file

    languages = Counter(
        c["language"].lower() for c in backend_chunks if isinstance(c.get("language"), str)
    )
    if not languages:
        return None

    most_common_language, _ = languages.most_common(1)[0]
    return _LANGUAGE_TO_STACK.get(most_common_language)


def _load_chunks(chunks_dir: Path) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(chunks_dir.glob("*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, list):
            chunks.extend(item for item in data if isinstance(item, dict))
    return chunks


def build_symbol_language_index(chunks_dir: Path = CHUNKS_DIR) -> dict[str, str]:
    """Maps symbol_id -> language for every chunk under chunks_dir (not
    filtered to backend -- this is for per-symbol lookups, e.g. deciding
    whether a specific target_symbols entry refers to frontend or backend
    code, unlike resolve_tech_stack()'s project-wide backend-only answer).
    Returns {} if chunks_dir doesn't exist or has nothing parseable --
    callers should treat that as "unknown," not an error."""
    if not chunks_dir.exists():
        return {}
    return {
        c["symbol_id"]: c["language"].lower()
        for c in _load_chunks(chunks_dir)
        if isinstance(c.get("symbol_id"), str) and isinstance(c.get("language"), str)
    }


def symbol_language(target_symbols: list[str], index: dict[str, str]) -> Optional[str]:
    """Looks up each target_symbols entry in a symbol-language index (see
    build_symbol_language_index()), returning the first match's language.
    None if no entry resolves (index empty, or none of the symbols are in it)."""
    for symbol_id in target_symbols:
        language = index.get(symbol_id)
        if language is not None:
            return language
    return None


def _resolve_from_extracted_requirements(contracts_dir: Path) -> Optional[str]:
    if not contracts_dir.exists():
        return None

    doc = _find_extracted_requirements(contracts_dir)
    if doc is None:
        return None

    tech_stack = doc.get("tech_stack")
    if not tech_stack:
        return None

    if isinstance(tech_stack, str):
        return tech_stack

    if isinstance(tech_stack, list):
        return _extract_stack_from_narrative(tech_stack)

    return None


def _extract_stack_from_narrative(entries: list) -> Optional[str]:
    """entries is a list of {"section": ..., "text": ...} dicts (prose from
    the SRS's Technology Stack section). Prefers a section explicitly about
    backend architecture, since that's what determines endpoint/function
    code generation; falls back to scanning every entry's text."""
    backend_entries = [
        e for e in entries
        if isinstance(e, dict) and "backend" in str(e.get("section", "")).lower()
    ]
    search_entries = backend_entries or entries

    combined_text = " ".join(
        str(e.get("text", "")) for e in search_entries if isinstance(e, dict)
    ).lower()

    for keyword, stack in _TEXT_KEYWORDS:
        if keyword in combined_text:
            return stack
    return None


def _find_extracted_requirements(contracts_dir: Path) -> Optional[dict]:
    """Look for the extracted-requirements JSON by name first; fall back to
    scanning every *.json in the folder for one that actually has a tech_stack key
    (exact filename isn't settled with the Design/Implementation teams yet)."""
    candidates = sorted(contracts_dir.glob("*.json"))
    named = [
        p for p in candidates
        if "extracted_requirement" in p.stem.lower() or "extracted-requirement" in p.stem.lower()
    ]

    for path in named + [p for p in candidates if p not in named]:
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and "tech_stack" in data:
            return data
    return None
