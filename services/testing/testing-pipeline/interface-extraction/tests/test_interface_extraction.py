"""Tests for Stage A (Interface Extraction) in the v1 layout.

Runs under pytest, or directly without it:
    python tests/test_interface_extraction.py

Covers the A1/A2/A3 chain (ported from v0) plus the v1 input adapters
(inputs.read_source_files / read_requirements) using real temp dirs so no
network or LLM is required.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chunker import chunk_codebase, is_test_file  # noqa: E402
from inputs import infer_tech_stack, read_requirements, read_source_files  # noqa: E402
from mapping_tree import build_mapping_tree  # noqa: E402
from strategy_planner import _build_messages, plan_test_strategy  # noqa: E402

PY_SOURCE = '''
class AgeValidationError(Exception):
    pass


def validate_age(age):
    if age < 0 or age > 120:
        raise AgeValidationError("bad")
    return True


class UserService:
    def __init__(self, repo):
        self.repo = repo

    def create_user(self, name, age):
        validate_age(age)
        self.repo.save({"name": name, "age": age})
        return True
'''

REQUIREMENTS = [
    {"id": "REQ-003", "text": "Age must be 0-120 inclusive", "acceptance_criteria": ["reject <0"]},
    {"id": "REQ-004", "text": "Persist the user", "acceptance_criteria": ["saved"]},
]


def _py_chunks():
    return chunk_codebase([{"path": "app/user.py", "language": "python", "content": PY_SOURCE}])


def _mapping_tree():
    return build_mapping_tree(_py_chunks())


# --- A1 ---
def test_a1_symbols():
    ids = {c["symbol_id"] for c in _py_chunks()}
    assert "app/user.py::validate_age" in ids
    assert "app/user.py::UserService.create_user" in ids
    assert is_test_file("tests/test_x.py") and not is_test_file("app/user.py")


# --- A2 ---
def test_a2_edges_and_fanin():
    syms = _mapping_tree()["symbols"]
    assert "app/user.py::validate_age" in syms["app/user.py::UserService.create_user"]["calls"]
    assert syms["app/user.py::validate_age"]["fan_in"] == 1
    assert "save" in syms["app/user.py::UserService.create_user"]["external_calls"]


# --- A3 grounding (F1) + coverage (F2) ---
def test_a3_grounding_and_coverage():
    def fake(_messages):
        return json.dumps({
            "test_files_impacted": [{
                "test_file_path": "tests/test_user.py", "test_type": "unit", "priority": "HIGH",
                "target_symbols": ["app/user.py::validate_age", "app/user.py::ghost"],
                "related_requirements": ["REQ-003", "REQ-999"],
            }],
            "test_coverage_impact": "", "historical_test_risks": "",
        })

    strat = plan_test_strategy(_mapping_tree(), REQUIREMENTS, llm=fake)
    entry = strat["test_files_impacted"][0]
    assert entry["target_symbols"] == ["app/user.py::validate_age"]      # ghost dropped
    assert entry["related_requirements"] == ["REQ-003"]                   # REQ-999 dropped
    assert strat["grounding"]["invalid_symbol_refs"] == ["app/user.py::ghost"]
    assert strat["requirements_coverage"]["uncovered"] == ["REQ-004"]


# --- A3 prompt signals (F3 hotspots + F4 DB/tech) ---
def test_a3_prompt_signals():
    user = _build_messages(_mapping_tree(), REQUIREMENTS, {"runtime": "python", "db": "sql"})[1]["content"]
    assert "HOTSPOTS" in user and "fan_in=" in user
    assert "[DB/IO]" in user and "pytest" in user


# --- v1 input adapters ---
def test_inputs_read_source_and_requirements():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "code").mkdir()
        (root / "code" / "user.py").write_text(PY_SOURCE, encoding="utf-8")
        (root / "code" / "notes.txt").write_text("ignore me", encoding="utf-8")  # non-source
        (root / "srs").mkdir()
        (root / "srs" / "requirements.json").write_text(json.dumps(REQUIREMENTS), encoding="utf-8")

        files = read_source_files(root / "code")
        assert len(files) == 1 and files[0]["path"] == "user.py" and files[0]["language"] == "python"
        assert infer_tech_stack(files) == {"runtime": "python"}

        reqs = read_requirements(root / "srs")
        assert [r["id"] for r in reqs] == ["REQ-003", "REQ-004"]


def _run_all():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")


if __name__ == "__main__":
    _run_all()
    print("\nAll Stage A (interface extraction) tests passed.")
