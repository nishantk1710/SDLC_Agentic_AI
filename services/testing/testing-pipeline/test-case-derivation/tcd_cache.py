"""Content-addressed cache for derived test cases (reference §7.5).

Keyed by a hash of (requirements + mapping_tree + strategy). Treated as an
optimization, not a determinism guarantee — even temperature=0 can drift across
model versions, so a miss simply re-derives. File-based under
``data/.cache/test-cases`` (git-ignored); disable with ``TESTING_TCD_CACHE=0``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, List, Optional

from tcd_config import CACHE_DIR, CACHE_ENABLED

logger = logging.getLogger(__name__)


def cache_key(requirements: Any, mapping_tree: Any, strategy: Any, stack: str = "") -> str:
    blob = json.dumps(
        {
            "requirements": requirements,
            "mapping_tree": mapping_tree,
            "strategy": strategy,
            "stack": stack,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def get(key: str) -> Optional[List[dict]]:
    if not CACHE_ENABLED:
        return None
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
        logger.info("Stage B cache hit: %s (%d cases)", key, len(cases))
        return cases
    except (OSError, json.JSONDecodeError):
        return None


def put(key: str, cases: List[dict]) -> None:
    if not CACHE_ENABLED:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    except OSError as exc:  # cache failures must never break derivation
        logger.warning("Stage B cache write failed: %s", exc)
