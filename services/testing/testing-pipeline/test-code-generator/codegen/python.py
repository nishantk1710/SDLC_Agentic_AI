"""
python.py — Step C's Python/pytest generator.

Splits cases by inferred kind (endpoint vs function need different pytest
fixtures/imports -- see schema.infer_kind(), since schema v2 dropped the
explicit target.kind field), then chunks each kind's cases into batches of
up to MAX_CASES_PER_BATCH -- one LLM call per batch. See base_generator.py
for why batching is by kind+size, not by req_id, and for
generate_batches()'s per-batch failure isolation (one bad batch doesn't
lose the others).

The source code under test is never included in the prompt -- only each
case's target_symbols/input/expected -- so the LLM cannot infer or
"correct" expected values from the implementation (see
llm/prompts/system_guardrails.md).
"""

import json
from collections import defaultdict

from codegen.base_generator import (
    MAX_CASES_PER_BATCH,
    GeneratedFile,
    Generator,
    assemble_generated_file,
    case_to_prompt_dict,
    chunk,
    generate_batches,
    load_prompt,
)
from llm.client import generate_structured
from llm.structured_output import GENERATED_FILE_SCHEMA, parse_generated_file
from schema import TestCase, infer_kind

_KIND_TO_PROMPT = {
    "endpoint": "python_pytest_endpoint.md",
    "function": "python_pytest_function.md",
}


class PythonGenerator(Generator):
    def __init__(self, max_cases_per_batch: int = MAX_CASES_PER_BATCH):
        self._system_prompt = load_prompt("system_guardrails.md")
        self._max_cases_per_batch = max_cases_per_batch

    def generate(self, cases: list[TestCase]) -> tuple[list[GeneratedFile], list[str]]:
        by_kind: dict[str, list[TestCase]] = defaultdict(list)
        for case in cases:
            by_kind[infer_kind(case)].append(case)

        generated: list[GeneratedFile] = []
        errors: list[str] = []
        for kind, kind_cases in by_kind.items():
            batches = chunk(kind_cases, self._max_cases_per_batch)
            files, batch_errors = generate_batches(
                batches,
                generate_one=lambda batch, batch_index, kind=kind: self._generate_batch(batch, kind, batch_index),
                label=f"python:{kind}",
            )
            generated.extend(files)
            errors.extend(batch_errors)
        return generated, errors

    def _generate_batch(self, cases: list[TestCase], kind: str, batch_index: int) -> GeneratedFile:
        user_prompt = self._build_user_prompt(cases, _KIND_TO_PROMPT[kind])
        raw = generate_structured(self._system_prompt, user_prompt, GENERATED_FILE_SCHEMA)
        output = parse_generated_file(raw)
        file_path = f"python/test_{kind}_batch{batch_index}.py"
        return assemble_generated_file(output, cases, file_path=file_path, runner="pytest")

    def _build_user_prompt(self, cases: list[TestCase], prompt_template: str) -> str:
        instructions = load_prompt(prompt_template)
        cases_json = [case_to_prompt_dict(c) for c in cases]
        return (
            f"{instructions}\n\n"
            f"Generate pytest test functions for these test cases "
            f"(JSON array, one entry per case):\n\n{json.dumps(cases_json, indent=2)}"
        )
