"""A3 — Test-case strategy planner (the single LLM step in Module A).

This is **our own** implementation. Its structure is informed by the zenseAi
reference agent ``test_strategy_agent.py`` — specifically its genuinely useful
parts: a strict output schema with defensive normalization and a prose
fallback so a malformed LLM reply never crashes the pipeline. We did NOT copy
its zenseAi coupling (DB credential lookup, PII guardrails, cost accounting,
``state`` dict, retrieved-ticket/knowledge context).

Key differences vs. the reference agent
---------------------------------------
* **Requirement-driven, not change/ticket-driven.** Input is our mapping tree
  + requirements, not a ``task_query`` + retrieved test-file chunks.
* **Source-symbol aware.** It reasons over source symbols from A2 (walking the
  mapping tree) rather than filtering pre-existing test files by filename.
* **Pluggable LLM.** Accepts any ``(messages) -> str`` callable, so tests inject
  a fake and real runs use the env-configured client. No key required to import.

Scope reminder: A3 decides *what to test and where* (a strategy). It does NOT
produce concrete inputs/expected values — that is Step B, intentionally not in
this module yet.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from llm_client import LLMCallable, get_default_llm
from logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# small coercion helpers (adapted, trimmed for POC, from the reference agent)
# ---------------------------------------------------------------------------
def _strip_code_fences(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = text.strip()
    t = re.sub(r"^\s*```(?:json|JSON)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _is_likely_json(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    return (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]"))


def _coerce_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        return "; ".join(str(x).strip() for x in v if str(x).strip())
    if isinstance(v, dict):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return str(v)


def _to_list_str(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        parts = [p.strip("•-* \t") for p in v.replace(",", "\n").splitlines()]
        return [p for p in parts if p]
    return [str(v).strip()]


# ---------------------------------------------------------------------------
# output models (our schema — a superset of the reference's test_strategy)
# ---------------------------------------------------------------------------
class TestFileImpact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    test_file_path: str = Field(description="Proposed/target test file path")
    test_type: str = Field(default="Unit Test")
    what_needs_testing: str = Field(default="")
    existing_or_new: str = Field(default="New - needs creation")
    priority: str = Field(default="MEDIUM")
    # our additions: link the strategy back to source + requirements
    target_symbols: List[str] = Field(default_factory=list)
    related_requirements: List[str] = Field(default_factory=list)
    reason: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        aliases = {
            "test_file": "test_file_path",
            "file": "test_file_path",
            "path": "test_file_path",
            "file_path": "test_file_path",
            "type": "test_type",
            "what_to_test": "what_needs_testing",
            "scope": "what_needs_testing",
            "status": "existing_or_new",
            "existing_new": "existing_or_new",
            "prio": "priority",
            "severity": "priority",
            "reason_retrieved": "reason",
            "why": "reason",
            "symbols": "target_symbols",
            "target_symbol": "target_symbols",
            "requirements": "related_requirements",
            "req_ids": "related_requirements",
            "requirement_ids": "related_requirements",
        }
        return {aliases.get(k.strip().lower(), k.strip().lower()): val for k, val in v.items()}

    @field_validator("target_symbols", "related_requirements", mode="before")
    @classmethod
    def _lists(cls, v: Any) -> List[str]:
        return _to_list_str(v)

    @field_validator("test_file_path", "what_needs_testing", "reason", mode="before")
    @classmethod
    def _strs(cls, v: Any) -> str:
        return _coerce_str(v)

    @field_validator("priority", mode="before")
    @classmethod
    def _norm_priority(cls, v: Any) -> str:
        t = str(v or "").strip().upper()
        t = {"CRITICAL": "HIGH", "P1": "HIGH", "P2": "MEDIUM", "P3": "LOW"}.get(t, t)
        return t if t in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"

    @field_validator("existing_or_new", mode="before")
    @classmethod
    def _norm_existing(cls, v: Any) -> str:
        t = str(v or "").strip().lower()
        if any(w in t for w in ("new", "create")):
            return "New - needs creation"
        if any(w in t for w in ("exist", "update", "modify")):
            return "Existing - needs update"
        return "New - needs creation"

    @field_validator("test_type", mode="before")
    @classmethod
    def _norm_type(cls, v: Any) -> str:
        t = str(v or "").strip().lower()
        for key, label in (
            ("unit", "Unit Test"),
            ("integration", "Integration Test"),
            ("e2e", "E2E Test"),
            ("end-to-end", "E2E Test"),
            ("end to end", "E2E Test"),
            ("performance", "Performance Test"),
            ("load", "Load Test"),
        ):
            if key in t:
                return label
        return str(v or "Unit Test").strip().title()


class TestStrategy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    test_files_impacted: List[TestFileImpact] = Field(default_factory=list)
    test_coverage_impact: str = Field(default="")
    historical_test_risks: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _normalize_top(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        aliases = {
            "tests_impacted": "test_files_impacted",
            "impacted_tests": "test_files_impacted",
            "coverage_impact": "test_coverage_impact",
            "coverage": "test_coverage_impact",
            "historical_risks": "historical_test_risks",
            "risks": "historical_test_risks",
        }
        return {aliases.get(k.strip().lower(), k.strip().lower()): val for k, val in v.items()}

    @field_validator("test_files_impacted", mode="before")
    @classmethod
    def _ensure_list(cls, v: Any) -> Any:
        if v is None:
            return []
        return v if isinstance(v, list) else [v]

    @field_validator("test_coverage_impact", "historical_test_risks", mode="before")
    @classmethod
    def _strs(cls, v: Any) -> str:
        return _coerce_str(v)


# ---------------------------------------------------------------------------
# prompt construction
# ---------------------------------------------------------------------------
_SYSTEM_INSTRUCTIONS = """You are a test-strategy planner for an automated testing pipeline.

You are given (1) a CODEBASE MAP of source symbols (functions/methods/classes,
their signatures and internal call edges) and (2) a list of REQUIREMENTS with
acceptance criteria.

Your job: decide WHAT to test and WHERE — a strategy, not concrete test inputs.
For each area that needs testing, name a target test file, the test type, which
source symbols and which requirement ids it covers, a priority, and why.

CRITICAL RULES:
- Base the strategy on the requirements. Use the codebase map only to know
  which symbols implement each requirement and how to reach them.
- Do NOT invent source symbols that are not in the codebase map.
- Every requirement should be covered by at least one entry (or explicitly
  called out as a coverage gap).
- Do NOT produce concrete input/expected values here — that is a later step.

PRIORITIZATION (F3): the map lists fan_in per symbol (how many callers it has =
blast radius) and a HOTSPOTS list of the highest-fan_in symbols. Treat high
fan_in symbols as higher risk and lean toward HIGH priority for them.

TECHNIQUE (F4): pick test_type using the TECH STACK and the per-symbol flags.
Symbols flagged [DB/IO] touch persistence/external I/O — cover them with an
Integration Test using the stated DB harness. Pure-logic symbols get Unit Tests.
Prefer the named TESTING TOOLS in what_needs_testing where relevant.

OUTPUT: STRICT JSON only, no prose, no markdown, matching this schema:
{
  "test_files_impacted": [
    {
      "test_file_path": "string",
      "test_type": "Unit Test | Integration Test | E2E Test | Performance Test | Load Test",
      "what_needs_testing": "string",
      "existing_or_new": "New - needs creation | Existing - needs update",
      "priority": "HIGH | MEDIUM | LOW",
      "target_symbols": ["<symbol_id>", ...],
      "related_requirements": ["REQ-...", ...],
      "reason": "string"
    }
  ],
  "test_coverage_impact": "string",
  "historical_test_risks": "string"
}
Use [] for empty arrays and "" for empty strings.
"""


# F4 — verbs that signal a symbol touches persistence / external I/O (DB harness needed).
_DB_IO_VERBS = {
    "save", "insert", "update", "delete", "query", "execute", "commit",
    "fetch", "persist", "find", "find_one", "insert_one", "update_one",
    "delete_one", "aggregate", "select", "scan",
}


def _fan_in(node: Dict[str, Any]) -> int:
    """Blast radius; falls back to len(called_by) for trees built before F3."""
    return node.get("fan_in", len(node.get("called_by", []) or []))


def _touches_db(external_calls: List[str]) -> bool:
    return any((c or "").lower() in _DB_IO_VERBS for c in external_calls or [])


def _tech_guide(tech_stack: Optional[Dict[str, Any]]):
    """F4 — resolve tech_stack into concrete technique guidance (deterministic)."""
    ts = tech_stack or {}
    runtime = str(ts.get("runtime", "")).lower()
    framework = str(ts.get("framework", "")).lower()
    db = str(ts.get("db", "")).lower()

    tool_by_key = {
        "python": "pytest; test APIs in-process via FastAPI/Starlette TestClient; use @pytest.mark.parametrize for boundary values",
        "node": "jest; test APIs in-process via Supertest",
        "express": "jest; test APIs in-process via Supertest",
        "react": "jest + React Testing Library (jsdom); mock network/fetch",
    }
    tool = tool_by_key.get(runtime) or tool_by_key.get(framework) or "the runtime's standard unit-test framework"

    if db in ("sql", "sqlite", "postgres", "postgresql", "mysql"):
        db_note = "For [DB/IO] symbols use an in-memory SQLite (:memory:) harness."
    elif db in ("mongo", "mongodb"):
        db_note = "For [DB/IO] symbols use an in-memory Mongo harness (mongomock / mongodb-memory-server)."
    else:
        db_note = "No DB harness unless a symbol is flagged [DB/IO]."

    stack_desc = " / ".join(p for p in (runtime, framework, db) if p) or "unspecified"
    return stack_desc, tool, db_note


def _hotspots(mapping_tree: Dict[str, Any], top_n: int = 5) -> List[str]:
    """F3 — highest-fan_in symbols, most-depended-on first (leaves excluded)."""
    symbols = mapping_tree.get("symbols", {}) or {}
    ranked = sorted(symbols.items(), key=lambda kv: _fan_in(kv[1]), reverse=True)
    return [f"- {sid} (fan_in={_fan_in(node)})" for sid, node in ranked[:top_n] if _fan_in(node) > 0]


def _format_mapping_tree(mapping_tree: Dict[str, Any], max_symbols: int = 200) -> str:
    symbols = mapping_tree.get("symbols", {}) or {}
    lines: List[str] = []
    for i, (sid, node) in enumerate(symbols.items()):
        if i >= max_symbols:
            lines.append(f"... ({len(symbols) - max_symbols} more symbols omitted)")
            break
        calls = node.get("calls", []) or []
        ext = node.get("external_calls", []) or []
        flags = []
        if node.get("is_test"):
            flags.append("TEST FILE")
        if _touches_db(ext):
            flags.append("DB/IO")
        flag = f"  [{', '.join(flags)}]" if flags else ""
        sig = node.get("signature") or node.get("symbol_type")
        lines.append(
            f"- {sid}{flag}\n"
            f"    signature: {sig}\n"
            f"    fan_in: {_fan_in(node)}\n"
            f"    calls(internal): {', '.join(calls) or '-'}\n"
            f"    calls(external): {', '.join(ext) or '-'}"
        )
    return "\n".join(lines) if lines else "No symbols extracted."


def _format_requirements(requirements: List[Dict[str, Any]]) -> str:
    if not requirements:
        return "No requirements provided."
    out: List[str] = []
    for r in requirements:
        rid = r.get("id", "REQ-?")
        text = r.get("text", "")
        ac = r.get("acceptance_criteria", []) or []
        ac_str = "".join(f"\n    - {c}" for c in ac) if ac else " (none)"
        out.append(f"{rid}: {text}\n  acceptance_criteria:{ac_str}")
    return "\n".join(out)


def _build_messages(
    mapping_tree: Dict[str, Any],
    requirements: List[Dict[str, Any]],
    tech_stack: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    stack_desc, tool, db_note = _tech_guide(tech_stack)          # F4
    hotspots = _hotspots(mapping_tree)                           # F3
    hotspots_block = "\n".join(hotspots) if hotspots else "(none — shallow call graph)"
    user = (
        f"TECH STACK: {stack_desc}\n"
        f"TESTING TOOLS: {tool}\n"
        f"DB HARNESS: {db_note}\n\n"
        "HOTSPOTS (highest blast radius — prioritize):\n"
        f"{hotspots_block}\n\n"
        "CODEBASE MAP (symbols flagged [DB/IO] touch persistence/external I/O):\n"
        f"{_format_mapping_tree(mapping_tree)}\n\n"
        "REQUIREMENTS:\n"
        f"{_format_requirements(requirements)}\n\n"
        "Produce the test strategy as strict JSON per the schema."
    )
    return [
        {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def _parse_strategy(raw: str) -> TestStrategy:
    """Parse an LLM reply into TestStrategy, tolerating fences/prose."""
    cleaned = _strip_code_fences(raw)
    if _is_likely_json(cleaned):
        try:
            return TestStrategy.model_validate_json(cleaned)
        except Exception:
            return TestStrategy.model_validate(json.loads(cleaned))
    # Prose fallback: keep the pipeline alive with a valid (empty) strategy.
    logger.warning("A3: LLM reply was not JSON; using prose fallback")
    return TestStrategy(
        test_files_impacted=[],
        test_coverage_impact=_coerce_str(cleaned),
        historical_test_risks="",
    )


# ---------------------------------------------------------------------------
# F1 grounding + F2 coverage (deterministic post-processing; no LLM, no prompt)
# ---------------------------------------------------------------------------
def _ground_and_cover(
    result: Dict[str, Any],
    mapping_tree: Dict[str, Any],
    requirements: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verify the LLM strategy against real data, in place.

    F1 (grounding): drop any ``target_symbols`` not present in the A2 mapping
    tree and any ``related_requirements`` not in the requirement-ID set; record
    what was dropped under ``grounding``.

    F2 (coverage): roll up which requirement IDs are covered by >=1 (grounded)
    entry vs. left uncovered, under ``requirements_coverage``.

    Both are additive keys; existing fields keep their shape.
    """
    known_symbols = set((mapping_tree or {}).get("symbols", {}).keys())
    known_reqs = {r.get("id") for r in (requirements or []) if r.get("id")}

    invalid_symbol_refs: List[str] = []
    invalid_requirement_refs: List[str] = []

    for entry in result.get("test_files_impacted", []) or []:
        kept_syms = []
        for s in entry.get("target_symbols", []) or []:
            (kept_syms if s in known_symbols else invalid_symbol_refs).append(s)
        entry["target_symbols"] = kept_syms

        kept_reqs = []
        for rid in entry.get("related_requirements", []) or []:
            (kept_reqs if rid in known_reqs else invalid_requirement_refs).append(rid)
        entry["related_requirements"] = kept_reqs

    result["grounding"] = {
        "invalid_symbol_refs": sorted(set(invalid_symbol_refs)),
        "invalid_requirement_refs": sorted(set(invalid_requirement_refs)),
    }

    covered = set()
    for entry in result.get("test_files_impacted", []) or []:
        covered.update(entry.get("related_requirements", []) or [])
    covered &= known_reqs
    result["requirements_coverage"] = {
        "covered": sorted(covered),
        "uncovered": sorted(known_reqs - covered),
    }

    if invalid_symbol_refs or invalid_requirement_refs:
        logger.warning(
            "A3 grounding: dropped %d unknown symbol ref(s), %d unknown requirement ref(s)",
            len(set(invalid_symbol_refs)),
            len(set(invalid_requirement_refs)),
        )
    if result["requirements_coverage"]["uncovered"]:
        logger.warning(
            "A3 coverage: %d requirement(s) uncovered: %s",
            len(result["requirements_coverage"]["uncovered"]),
            result["requirements_coverage"]["uncovered"],
        )
    return result


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------
def plan_test_strategy(
    mapping_tree: Dict[str, Any],
    requirements: List[Dict[str, Any]],
    llm: Optional[LLMCallable] = None,
    tech_stack: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """A3 entry point: (mapping_tree + requirements) -> ``test_strategy`` dict.

    ``llm`` is any ``(messages) -> str`` callable. If omitted, an env-configured
    client is built lazily (needs ``LLM_API_KEY``). On any failure a valid but
    empty strategy is returned so callers downstream never crash.
    """
    llm = llm or get_default_llm()
    messages = _build_messages(mapping_tree, requirements, tech_stack)

    try:
        raw = llm(messages)
        strategy = _parse_strategy(raw)
        result = strategy.model_dump()
        result = _ground_and_cover(result, mapping_tree, requirements)  # F1 + F2
        logger.info(
            "A3: strategy with %d impacted test file(s)",
            len(result.get("test_files_impacted", [])),
        )
        return result
    except Exception as exc:  # keep Module A resilient for the POC
        logger.error("A3: strategy generation failed: %s", exc, exc_info=True)
        result = {
            "test_files_impacted": [],
            "test_coverage_impact": f"Strategy generation failed: {exc}",
            "historical_test_risks": "",
        }
        return _ground_and_cover(result, mapping_tree, requirements)
