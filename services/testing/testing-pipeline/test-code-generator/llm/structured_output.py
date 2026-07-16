"""
structured_output.py — the forced-output shape for Step C's LLM calls.

The LLM must respond via a single tool call matching GENERATED_FILE_SCHEMA
(Anthropic tool-use), never markdown-fenced prose. This is what lets
validators/traceability_check.py mechanically confirm every assertion
literal traces back to a test case's `expected` field via
expected_value_provenance, instead of trusting the LLM's own account of
what it did.
"""

from typing import Any

from pydantic import BaseModel


class ExpectedValueProvenance(BaseModel):
    source_case_id: str
    expected_key: str  # dot-path into a dict expected value (e.g. "json.user_id"), or "__value__" for a scalar expected
    expected_value: Any


class GeneratedTestFunction(BaseModel):
    name: str
    source_test_case_ids: list[str]
    code: str
    expected_value_provenance: list[ExpectedValueProvenance]


class GeneratedFileOutput(BaseModel):
    file_path: str
    imports: list[str]
    test_functions: list[GeneratedTestFunction]


GENERATED_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {"type": "string"},
        "imports": {"type": "array", "items": {"type": "string"}},
        "test_functions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source_test_case_ids": {"type": "array", "items": {"type": "string"}},
                    "code": {"type": "string"},
                    "expected_value_provenance": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_case_id": {"type": "string"},
                                "expected_key": {
                                    "type": "string",
                                    "description": (
                                        "Dot-path into the test case's expected value if it's a "
                                        "dict (e.g. 'json.user_id' for expected={'status_code': 200, "
                                        "'json': {'user_id': ...}}), or the literal string '__value__' "
                                        "if the test case's expected value is a scalar (bool/int/float/str)."
                                    ),
                                },
                                "expected_value": {
                                    "description": (
                                        "The exact value from the test case's expected field, copied "
                                        "verbatim -- including placeholder tokens like '__any_string__' "
                                        "or '__any_bool__' if that's literally what the test case has. "
                                        "Never a runtime value your assertion computed."
                                    )
                                },
                            },
                            "required": ["source_case_id", "expected_key", "expected_value"],
                        },
                    },
                },
                "required": ["name", "source_test_case_ids", "code", "expected_value_provenance"],
            },
        },
    },
    "required": ["file_path", "imports", "test_functions"],
}


def parse_generated_file(raw: dict) -> GeneratedFileOutput:
    return GeneratedFileOutput.model_validate(raw)
