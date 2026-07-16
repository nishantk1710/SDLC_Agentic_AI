"""
schema.py — the shared TestCase shape every generator consumes.

This mirrors services/testing/data/test_cases.json, produced by Step B
(test-case derivation). Generators (Step C) never invent fields — they only
read what's here. Pydantic validates on load so a schema drift in Step B's
output fails loudly at load time instead of silently misgenerating tests.

Schema v2: the real Step B output (source="direct_llm") has no explicit
target.kind field anymore -- it was replaced by target_symbols (a list of
fully-qualified symbol paths) with no endpoint/function label. infer_kind()
below is the one place that decides endpoint-vs-function, so
dispatcher.py/codegen/*.py all agree instead of drifting into separate
copies of the same heuristic.
"""

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel

CaseType = Literal["happy_path", "boundary", "invalid_input", "error_handling", "e2e_flow"]
InferredKind = Literal["endpoint", "function"]


class TestCase(BaseModel):
    __test__ = False  # not a pytest test class -- name collides with pytest's "Test*" collection convention

    id: str
    req_id: str
    type: CaseType
    input: Union[dict[str, Any], list[Any]] = {}
    expected: Union[dict[str, Any], bool, int, float, str] = {}
    notes: str = ""
    target_symbols: list[str] = []
    steps: Optional[list[dict[str, Any]]] = None  # only for type == "e2e_flow"


class TestCaseFile(BaseModel):
    schema_version: str
    source: str
    scope_note: Optional[str] = None  # dropped in the real (schema v2) output
    test_cases: list[TestCase]
    grounding: Optional[dict[str, Any]] = None  # {invalid_symbol_refs, cases_with_unknown_req} -- not used by Step C
    requirements_coverage: Optional[dict[str, Any]] = None  # {covered, uncovered} -- not used by Step C


def infer_kind(case: TestCase) -> InferredKind:
    """A case is endpoint-shaped if `input` is a dict carrying an HTTP
    method + path; otherwise it's a direct function call against
    target_symbols. There's no explicit field for this in the real data
    (schema v2 dropped target.kind), so this is the one place the
    heuristic lives -- every real endpoint case has input.method/input.path,
    every real function case doesn't."""
    if isinstance(case.input, dict) and "method" in case.input and "path" in case.input:
        return "endpoint"
    return "function"


def load_test_cases(path: str) -> TestCaseFile:
    """Load and validate a test_cases.json file (as produced by Step B)."""
    import json

    with open(path) as f:
        data = json.load(f)
    return TestCaseFile.model_validate(data)  # raises pydantic.ValidationError on drift
