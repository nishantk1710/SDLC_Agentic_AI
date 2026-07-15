"""Tests for Stage B (Test-Case Derivation). No network / no real LLM.

Run under pytest, or directly:
    python tests/test_test_case_derivation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mcp_adapter  # noqa: E402
from derivation_router import derive_test_cases  # noqa: E402
from direct_planner import plan_test_cases  # noqa: E402
from test_case_derivation import _ground_and_complete  # noqa: E402
from test_case_models import parse_test_cases  # noqa: E402

MAPPING_TREE = {
    "symbols": {
        "app/user.py::validate_age": {"signature": "validate_age(age)"},
        "app/user.py::UserService.create_user": {"signature": "create_user(self, name, age)"},
    }
}
REQUIREMENTS = [
    {"id": "REQ-003", "text": "Age must be 0-120 inclusive", "acceptance_criteria": ["reject <0", "reject >120"]},
    {"id": "REQ-004", "text": "Persist the user", "acceptance_criteria": ["saved"]},
]
STRATEGY = {
    "test_files_impacted": [
        {"test_type": "Unit Test", "priority": "HIGH", "related_requirements": ["REQ-003"],
         "target_symbols": ["app/user.py::validate_age"], "what_needs_testing": "age bounds"}
    ]
}


def _fake_llm(_messages):
    return json.dumps({
        "test_cases": [
            {"id": "TC-003-1", "req_id": "REQ-003", "type": "boundary",
             "input": {"age": 120}, "expected": {"status": "accepted"},
             "target_symbols": ["app/user.py::validate_age", "app/user.py::ghost"]},
            {"req_id": "REQ-003", "type": "invalid",  # no id -> auto-assigned; 'invalid' -> invalid_input
             "input": {"age": 200}, "expected": {"status": "rejected"},
             "target_symbols": ["app/user.py::validate_age"]},
        ]
    })


# --- parsing ---
def test_parse_variants():
    assert len(parse_test_cases('[{"id":"a","req_id":"R","type":"happy"}]')) == 1        # bare list
    assert len(parse_test_cases('{"test_cases":[{"id":"a","req_id":"R","type":"x"}]}')) == 1  # wrapped
    assert len(parse_test_cases("```json\n[]\n```")) == 0                                # fenced
    assert parse_test_cases("sorry, no json here") == []                                 # prose -> []
    # type normalization
    assert parse_test_cases('[{"id":"a","req_id":"R","type":"negative"}]')[0]["type"] == "invalid_input"


# --- direct planner ---
def test_direct_planner_with_fake_llm():
    cases = plan_test_cases(REQUIREMENTS, MAPPING_TREE, STRATEGY, llm=_fake_llm)
    assert len(cases) == 2
    assert cases[0]["type"] == "boundary"
    assert cases[1]["type"] == "invalid_input"  # 'invalid' normalized


# --- router: MCP inert by default -> direct-LLM ---
def test_mcp_unavailable_by_default():
    assert mcp_adapter.is_available() is False
    assert mcp_adapter.health() is False


def test_router_falls_back_to_direct():
    cases, source = derive_test_cases(REQUIREMENTS, MAPPING_TREE, STRATEGY, llm=_fake_llm, use_cache=False)
    assert source == "direct_llm"
    assert len(cases) == 2


# --- grounding + completeness ---
def test_ground_and_complete():
    cases = plan_test_cases(REQUIREMENTS, MAPPING_TREE, STRATEGY, llm=_fake_llm)
    checks = _ground_and_complete(cases, MAPPING_TREE, REQUIREMENTS)
    # ghost symbol dropped from the first case
    assert cases[0]["target_symbols"] == ["app/user.py::validate_age"]
    assert checks["grounding"]["invalid_symbol_refs"] == ["app/user.py::ghost"]
    # second case had no id -> auto-assigned
    assert cases[1]["id"].startswith("TC-003-")
    # REQ-003 covered, REQ-004 not
    assert checks["requirements_coverage"]["covered"] == ["REQ-003"]
    assert checks["requirements_coverage"]["uncovered"] == ["REQ-004"]


def _run_all():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")


if __name__ == "__main__":
    _run_all()
    print("\nAll Stage B (test-case derivation) tests passed.")
