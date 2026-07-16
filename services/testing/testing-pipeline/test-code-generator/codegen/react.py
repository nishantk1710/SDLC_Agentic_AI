"""
react.py — Step C's React component generator (Jest + React Testing Library).

Currently unreachable via router/dispatcher.py: schema v2 (the real Step B
output) dropped target.kind entirely, so there's no field left that marks
a case as "component"-shaped -- dispatcher's routing_key_for() only ever
returns "e2e" or the resolved backend tech_stack now. This generator is
kept, registered, and tested (so it's ready the moment Step B's schema
gains a way to signal a component case), but nothing routes to it yet.
Not a bug to fix here -- see schema.py's docstring and the "Schema v2"
section of the plan.

Chunks cases to MAX_CASES_PER_BATCH, one LLM call per batch, with per-batch
failure isolation via generate_batches() -- same reasoning as python.py/node.py.
"""

import json

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
from schema import TestCase

_PROMPT = "react_jest_component.md"


class ReactGenerator(Generator):
    def __init__(self, max_cases_per_batch: int = MAX_CASES_PER_BATCH):
        self._system_prompt = load_prompt("system_guardrails.md")
        self._max_cases_per_batch = max_cases_per_batch

    def generate(self, cases: list[TestCase]) -> tuple[list[GeneratedFile], list[str]]:
        batches = chunk(cases, self._max_cases_per_batch)
        return generate_batches(batches, generate_one=self._generate_batch, label="react:component")

    def _generate_batch(self, cases: list[TestCase], batch_index: int) -> GeneratedFile:
        user_prompt = self._build_user_prompt(cases)
        raw = generate_structured(self._system_prompt, user_prompt, GENERATED_FILE_SCHEMA)
        output = parse_generated_file(raw)
        file_path = f"react/test_component_batch{batch_index}.test.jsx"
        return assemble_generated_file(output, cases, file_path=file_path, runner="jest")

    def _build_user_prompt(self, cases: list[TestCase]) -> str:
        instructions = load_prompt(_PROMPT)
        cases_json = [case_to_prompt_dict(c) for c in cases]
        return (
            f"{instructions}\n\n"
            f"Generate Jest/RTL test functions for these test cases "
            f"(JSON array, one entry per case):\n\n{json.dumps(cases_json, indent=2)}"
        )
