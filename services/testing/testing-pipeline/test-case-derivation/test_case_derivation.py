"""Test-Case Derivation stage orchestrator (Stage B of the Testing Phase).

Reads Stage A's artifacts (requirements + mapping tree + strategy), derives
concrete test cases via the router (MCP if available, else direct-LLM), then
deterministically:

  * **grounds** each case — drops ``target_symbols`` absent from the mapping tree,
    flags cases whose ``req_id`` is unknown (reference §7.1 discipline);
  * assigns stable ids where the model omitted them;
  * computes **requirement coverage** — every requirement must have >= 1 case,
    else it is reported uncovered (reference §7.2).

Writes ``data/test-cases.json``. ``run_test_case_derivation`` is what
``services/testing/main.py`` calls as Stage B; it also accepts in-memory inputs
so the pipeline can pass Stage A's outputs directly.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import derivation_router
from tcd_config import (
    MAPPING_TREE_PATH,
    REQUIREMENTS_PATH,
    STRATEGY_PATH,
    TECH_STACK_PATH,
    TEST_CASES_PATH,
)
from tcd_llm_client import LLMCallable

logger = logging.getLogger(__name__)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Stage B: could not read %s; using default", path)
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _req_number(req_id: str, fallback: int) -> str:
    m = re.search(r"(\d+)", req_id or "")
    return m.group(1) if m else f"{fallback:03d}"


def _ground_and_complete(
    cases: List[Dict[str, Any]],
    mapping_tree: Dict[str, Any],
    requirements: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Drop hallucinated symbol refs, assign missing ids, compute coverage."""
    known_symbols = set((mapping_tree or {}).get("symbols", {}).keys())
    known_reqs = [r.get("id") for r in (requirements or []) if r.get("id")]
    known_req_set = set(known_reqs)

    invalid_symbol_refs: List[str] = []
    cases_with_unknown_req: List[str] = []
    per_req_counter: Dict[str, int] = {}

    for idx, case in enumerate(cases):
        # ground target_symbols against the mapping tree
        kept = []
        for s in case.get("target_symbols", []) or []:
            (kept if s in known_symbols else invalid_symbol_refs).append(s)
        case["target_symbols"] = kept

        # assign a stable id if missing
        if not case.get("id"):
            num = _req_number(case.get("req_id", ""), idx)
            per_req_counter[num] = per_req_counter.get(num, 0) + 1
            case["id"] = f"TC-{num}-{per_req_counter[num]}"

        if case.get("req_id") not in known_req_set:
            cases_with_unknown_req.append(case["id"])

    covered = sorted({c.get("req_id") for c in cases if c.get("req_id") in known_req_set})
    uncovered = sorted(known_req_set - set(covered))

    if invalid_symbol_refs:
        logger.warning("Stage B grounding: dropped %d unknown symbol ref(s)", len(set(invalid_symbol_refs)))
    if uncovered:
        logger.warning("Stage B coverage: %d requirement(s) with no test case: %s", len(uncovered), uncovered)

    return {
        "grounding": {
            "invalid_symbol_refs": sorted(set(invalid_symbol_refs)),
            "cases_with_unknown_req": cases_with_unknown_req,
        },
        "requirements_coverage": {"covered": covered, "uncovered": uncovered},
    }


def run_test_case_derivation(
    requirements: Optional[List[Dict[str, Any]]] = None,
    mapping_tree: Optional[Dict[str, Any]] = None,
    strategy: Optional[Dict[str, Any]] = None,
    tech_stack: Optional[Dict[str, Any]] = None,
    llm: Optional[LLMCallable] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Execute Stage B end to end and persist ``test-cases.json``.

    Any input left as ``None`` is loaded from Stage A's artifact in ``data/``.
    ``tech_stack`` seeds stack detection (used from Step 6 onward); when absent
    it is loaded from Stage A's ``tech-stack.json`` and detection later falls
    back to the mapping tree's per-symbol languages.
    """
    if requirements is None:
        requirements = _read_json(REQUIREMENTS_PATH, [])
    if mapping_tree is None:
        mapping_tree = _read_json(MAPPING_TREE_PATH, {})
    if strategy is None:
        strategy = _read_json(STRATEGY_PATH, {})
    if tech_stack is None:
        tech_stack = _read_json(TECH_STACK_PATH, {})

    logger.info(
        "Stage B start: %d requirement(s), %d symbol(s), %d strategy entrie(s), tech_stack=%s",
        len(requirements),
        len((mapping_tree or {}).get("symbols", {})),
        len((strategy or {}).get("test_files_impacted", [])),
        tech_stack,
    )

    cases, source = derivation_router.derive_test_cases(
        requirements, mapping_tree, strategy, tech_stack=tech_stack, llm=llm, use_cache=use_cache
    )
    checks = _ground_and_complete(cases, mapping_tree, requirements)

    artifact = {
        "schema_version": "1.0",
        "source": source,
        "test_cases": cases,
        **checks,
    }
    _write_json(TEST_CASES_PATH, artifact)

    logger.info(
        "Stage B done: %d case(s) via %s; coverage %d/%d requirements -> %s",
        len(cases),
        source,
        len(checks["requirements_coverage"]["covered"]),
        len(requirements),
        TEST_CASES_PATH,
    )

    return {
        "status": "OK",
        "stage": "test-case-derivation",
        "summary": {
            "source": source,
            "tech_stack": tech_stack,
            "test_cases": len(cases),
            "by_type": _count_by_type(cases),
            "requirements_coverage": checks["requirements_coverage"],
            "grounding": checks["grounding"],
        },
        "artifacts": {"test_cases": str(TEST_CASES_PATH)},
        "data": {"test_cases": artifact},
    }


def _count_by_type(cases: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for c in cases:
        counts[c.get("type", "?")] = counts.get(c.get("type", "?"), 0) + 1
    return counts
