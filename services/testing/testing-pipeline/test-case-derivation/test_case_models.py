"""Pydantic models + tolerant parsing for Stage B's ``test_cases`` artifact.

A test case is concrete: an ``input`` and the ``expected`` result for one
requirement. Expected values must trace to requirements/acceptance criteria
(reference §7.1) — enforced by the planner prompt; the models just validate and
normalize whatever the LLM (or MCP tool) returns so downstream stages get a
stable shape regardless of source.
"""

from __future__ import annotations

import json
import re
from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- functional case types (reference §7.4) ---
_TYPE_ALIASES = {
    "happy": "happy_path",
    "happy_path": "happy_path",
    "happypath": "happy_path",
    "positive": "happy_path",
    "boundary": "boundary",
    "edge": "boundary",
    "edge_case": "boundary",
    "invalid": "invalid_input",
    "invalid_input": "invalid_input",
    "negative": "invalid_input",
    "error": "error_handling",
    "error_handling": "error_handling",
    "exception": "error_handling",
    "generated": "generated",  # full test file emitted by the MCP genie
}


def _strip_code_fences(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = text.strip()
    t = re.sub(r"^\s*```(?:json|JSON)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


class TestCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default="")
    req_id: str = Field(default="")
    type: str = Field(default="happy_path")
    input: Any = None
    expected: Any = None
    notes: str = Field(default="")
    target_symbols: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        alias = {
            "test_id": "id",
            "tc_id": "id",
            "requirement": "req_id",
            "requirement_id": "req_id",
            "reqid": "req_id",
            "case_type": "type",
            "category": "type",
            "inputs": "input",
            "expected_output": "expected",
            "expected_result": "expected",
            "symbols": "target_symbols",
            "targets": "target_symbols",
        }
        return {alias.get(k.strip().lower(), k.strip().lower()): val for k, val in v.items()}

    @field_validator("type", mode="before")
    @classmethod
    def _norm_type(cls, v: Any) -> str:
        key = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
        return _TYPE_ALIASES.get(key, "happy_path")

    @field_validator("id", "req_id", "notes", mode="before")
    @classmethod
    def _as_str(cls, v: Any) -> str:
        return "" if v is None else str(v).strip()

    @field_validator("target_symbols", mode="before")
    @classmethod
    def _as_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return [str(x) for x in v]


class TestCaseSet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0"
    test_cases: List[TestCase] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_bare_list(cls, v: Any) -> Any:
        # The LLM/MCP may return a bare list OR {"test_cases": [...]}.
        if isinstance(v, list):
            return {"test_cases": v}
        if isinstance(v, dict) and "test_cases" not in v:
            for alt in ("cases", "testCases", "test_case"):
                if alt in v:
                    return {**v, "test_cases": v[alt]}
        return v


def parse_test_cases(raw: Any) -> List[dict]:
    """Parse an LLM/MCP reply into a normalized list of test-case dicts.

    Tolerates code fences, a bare JSON array, or a wrapped object. Returns [] on
    unparseable prose (the caller decides how to handle an empty result).
    """
    if isinstance(raw, (list, dict)):
        data: Any = raw
    else:
        cleaned = _strip_code_fences(str(raw))
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            return []
    try:
        return [tc.model_dump() for tc in TestCaseSet.model_validate(data).test_cases]
    except Exception:
        return []
