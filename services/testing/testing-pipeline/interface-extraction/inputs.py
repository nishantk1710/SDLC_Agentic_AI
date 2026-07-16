"""Adapt the Source Loader Service's output into Module A's inputs.

The Source Loader writes files to disk under ``data/input`` (source code to
``unzipped-code/``, SRS verbatim to ``SRS/``). This module reads those back into
the shapes Module A expects:

    read_source_files() -> [{"path", "language", "content"}]   (A1 input)
    read_requirements() -> [{"id", "text", "acceptance_criteria"}]  (A3 input)

NOTE (POC shim): the SRS artifact is copied verbatim as *any* file type, and the
requirements contract (``contracts/shared``) is not frozen yet. So
``read_requirements`` looks for a JSON requirements file in the SRS drop; when
the contract lands, replace the JSON-scan with the real parser — nothing else in
Module A changes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from ie_config import MAX_SOURCE_BYTES, SOURCE_EXTENSIONS, SRS_DIR, UNZIPPED_CODE_DIR

logger = logging.getLogger(__name__)

_SKIP_NAMES = {".gitkeep"}


def read_source_files(root: Path = UNZIPPED_CODE_DIR) -> List[Dict[str, str]]:
    """Walk the unzipped source tree and return code-only files for A1."""
    if not root.exists():
        logger.warning("A1 input: source dir does not exist: %s", root)
        return []

    files: List[Dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in _SKIP_NAMES:
            continue
        language = SOURCE_EXTENSIONS.get(path.suffix.lower())
        if language is None:
            continue  # not a recognized source file
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                logger.info("A1 input: skipping large file %s", path)
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("A1 input: could not read %s (%s)", path, exc)
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "language": language,
                "content": content,
            }
        )

    logger.info("A1 input: %d source file(s) from %s", len(files), root)
    return files


def _normalize_requirement(item: Any, idx: int) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"id": f"REQ-{idx + 1:03d}", "text": str(item), "acceptance_criteria": []}
    rid = item.get("id") or item.get("req_id") or f"REQ-{idx + 1:03d}"
    text = item.get("text") or item.get("requirement") or item.get("description") or ""
    ac = item.get("acceptance_criteria") or item.get("acceptanceCriteria") or []
    if isinstance(ac, str):
        ac = [ac]
    return {"id": str(rid), "text": str(text), "acceptance_criteria": list(ac)}


def read_requirements(root: Path = SRS_DIR) -> List[Dict[str, Any]]:
    """Read requirements from the SRS drop (POC: first JSON file found).

    Accepts either a top-level list of requirements, or an object with a
    ``requirements`` array. Returns [] (with a warning) if none is found —
    Module A still runs; A3 simply reports the requirements as uncovered.
    """
    if not root.exists():
        logger.warning("A3 input: SRS dir does not exist: %s", root)
        return []

    for jf in sorted(root.rglob("*.json")):
        if jf.name in _SKIP_NAMES:
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("A3 input: could not parse %s (%s)", jf, exc)
            continue
        raw = data.get("requirements") if isinstance(data, dict) else data
        if isinstance(raw, list):
            reqs = [_normalize_requirement(r, i) for i, r in enumerate(raw)]
            logger.info("A3 input: %d requirement(s) from %s", len(reqs), jf.name)
            return reqs

    logger.warning(
        "A3 input: no JSON requirements found under %s; proceeding with none "
        "(POC shim — replace with the frozen SRS parser when available).",
        root,
    )
    return []


# runtime label the codegen/execution stages will route on later.
_LANG_TO_RUNTIME = {"python": "python", "javascript": "node", "typescript": "node", "java": "java"}


def infer_tech_stack(source_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Best-effort tech_stack from the source — full-stack aware.

    Detects the backend framework and whether a React frontend is present by a
    light content/extension scan, so a full-stack repo is reported as such (not
    collapsed to whichever language has the most files). Shape::

        {"runtime": "python", "framework": "fastapi",
         "frontend": {"present": true, "framework": "react"},
         "full_stack": true}
    """
    counts: Dict[str, int] = {}
    backend_framework = ""
    frontend_framework = ""
    has_python = has_express = False

    for f in source_files:
        lang = (f.get("language") or "").lower()
        counts[lang] = counts.get(lang, 0) + 1
        content = (f.get("content") or "").lower()
        path = (f.get("path") or "").lower()

        if lang == "python":
            has_python = True
            for marker in ("fastapi", "flask", "django"):
                if marker in content and not backend_framework:
                    backend_framework = marker
        if lang in ("javascript", "typescript"):
            if path.endswith((".jsx", ".tsx")) or "from \"react\"" in content or "from 'react'" in content or "react-dom" in content:
                frontend_framework = "react"
            if "require('express')" in content or 'require("express")' in content or "from \"express\"" in content:
                has_express = True
                backend_framework = backend_framework or "express"

    if not counts:
        return {}

    # Primary runtime: prefer a real backend over a file-count majority.
    if has_python:
        runtime = "python"
    elif has_express:
        runtime = "node"
    else:
        top_lang = max(counts, key=counts.get)
        runtime = _LANG_TO_RUNTIME.get(top_lang, top_lang)

    ts: Dict[str, Any] = {"runtime": runtime}
    if backend_framework:
        ts["framework"] = backend_framework
    if frontend_framework:
        ts["frontend"] = {"present": True, "framework": frontend_framework}
        # full-stack = a backend AND a frontend both present
        ts["full_stack"] = has_python or bool(backend_framework)
    return ts
