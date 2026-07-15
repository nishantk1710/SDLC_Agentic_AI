"""Interface Extraction stage orchestrator (Stage A of the Testing Phase).

Runs A1 -> A2 -> A3 over the Source Loader Service's output and writes three
artifacts into ``data/``:

    data/Chunks/chunks.json     (A1)
    data/mapping-tree.json      (A2)
    data/test-strategy.json     (A3)

``run_interface_extraction`` is what ``services/testing/main.py`` calls as
Stage A. A3 needs an LLM; if none is configured it degrades to a valid-but-empty
strategy (never crashes the pipeline), so the seam is safe to wire immediately.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from chunker import chunk_codebase
from ie_config import (
    CHUNKS_PATH,
    MAPPING_TREE_PATH,
    REQUIREMENTS_PATH,
    STRATEGY_PATH,
    TECH_STACK_PATH,
)
from inputs import infer_tech_stack, read_requirements, read_source_files
from llm_client import LLMCallable
from mapping_tree import build_mapping_tree
from strategy_planner import plan_test_strategy

logger = logging.getLogger(__name__)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_interface_extraction(llm: Optional[LLMCallable] = None) -> Dict[str, Any]:
    """Execute Stage A end to end and persist its artifacts.

    Returns a summary dict (safe to embed in the pipeline's JSON response) plus
    the full artifacts for any in-process caller.
    """
    source_files = read_source_files()
    requirements = read_requirements()
    tech_stack = infer_tech_stack(source_files)

    logger.info(
        "Stage A start: %d source file(s), %d requirement(s), tech_stack=%s",
        len(source_files), len(requirements), tech_stack,
    )

    chunks = chunk_codebase(source_files, tech_stack)                # A1
    mapping_tree = build_mapping_tree(chunks)                        # A2
    strategy = plan_test_strategy(                                   # A3 (LLM)
        mapping_tree, requirements, llm=llm, tech_stack=tech_stack
    )

    _write_json(CHUNKS_PATH, chunks)
    _write_json(MAPPING_TREE_PATH, mapping_tree)
    _write_json(STRATEGY_PATH, strategy)
    _write_json(REQUIREMENTS_PATH, requirements)
    _write_json(TECH_STACK_PATH, tech_stack)

    logger.info(
        "Stage A done: %d chunks, %d symbols, %d strategy entries -> %s",
        len(chunks),
        mapping_tree.get("stats", {}).get("symbol_count", 0),
        len(strategy.get("test_files_impacted", [])),
        CHUNKS_PATH.parent.parent,
    )

    return {
        "status": "OK",
        "stage": "interface-extraction",
        "summary": {
            "source_files": len(source_files),
            "requirements": len(requirements),
            "chunks": len(chunks),
            "symbols": mapping_tree.get("stats", {}).get("symbol_count", 0),
            "edges": mapping_tree.get("stats", {}).get("edge_count", 0),
            "strategy_entries": len(strategy.get("test_files_impacted", [])),
            "requirements_coverage": strategy.get("requirements_coverage", {}),
        },
        "artifacts": {
            "chunks": str(CHUNKS_PATH),
            "mapping_tree": str(MAPPING_TREE_PATH),
            "test_strategy": str(STRATEGY_PATH),
        },
        # full payloads for in-process callers (not just the file paths)
        "data": {
            "requirements": requirements,
            "tech_stack": tech_stack,
            "chunks": chunks,
            "mapping_tree": mapping_tree,
            "test_strategy": strategy,
        },
    }
