"""
traceability_check.py — the core guardrail (reference doc §0/§6): confirms
every literal a generated test asserts on actually appears, unmodified, in
the source test case's `expected` value, via the provenance the LLM was
required to report. This is what makes "expected values trace to
requirements, never to generated code" a checked property instead of an
assumption about the LLM's behavior.

Schema v2: `expected` can be a bool/int/float/str (not just a dict), and
dict-shaped `expected` can be nested (e.g. {"status_code": 200, "json":
{"user_id": "__any_string__"}}). _lookup_expected() handles both:
`expected_key == "__value__"` means "the whole expected value" (used for
scalar expected); otherwise a dot-path ("json.user_id") traverses into
nested dicts.
"""

from typing import Any

from codegen.base_generator import GeneratedFile
from schema import TestCase

_MISSING = object()


def _lookup_expected(expected: Any, key: str) -> Any:
    """Looks up `key` within `expected`. Returns _MISSING if it doesn't resolve."""
    if key == "__value__":
        return expected
    if not isinstance(expected, dict):
        return _MISSING
    value: Any = expected
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def check_traceability(generated_file: GeneratedFile, cases_by_id: dict[str, TestCase]) -> list[str]:
    """Returns a list of error strings; empty means every provenance entry
    checks out and every case with an expected value is covered by at least one."""
    errors: list[str] = []
    covered_case_ids: set[str] = set()

    for entry in generated_file.provenance:
        case = cases_by_id.get(entry.source_case_id)
        if case is None:
            errors.append(f"provenance references unknown test case id {entry.source_case_id!r}")
            continue

        actual_value = _lookup_expected(case.expected, entry.expected_key)
        if actual_value is _MISSING:
            errors.append(
                f"{entry.source_case_id}: provenance claims expected key "
                f"{entry.expected_key!r}, but that doesn't resolve in the case's expected value"
            )
            continue

        if actual_value != entry.expected_value:
            errors.append(
                f"{entry.source_case_id}: provenance value for {entry.expected_key!r} is "
                f"{entry.expected_value!r}, but the test case's real expected value is "
                f"{actual_value!r} -- the LLM altered an expected value"
            )
            continue

        covered_case_ids.add(entry.source_case_id)

    # Coverage: every case this file claims to cover, with a real expected
    # value, should have at least one provenance entry. Compare against the
    # TestCase default ({}) explicitly, not truthiness -- a real but falsy
    # scalar (False, 0, "") must still count as "has an expected value".
    for case_id in generated_file.source_test_case_ids:
        case = cases_by_id.get(case_id)
        if case is not None and case.expected != {} and case_id not in covered_case_ids:
            errors.append(
                f"{case_id}: has an expected value but no matching provenance entry "
                f"-- possible ungrounded assertion"
            )

    return errors
