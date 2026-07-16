"""
node.py — Step C's Node/Express + Jest/Supertest generator.

Mirrors codegen/python.py's structure exactly (split by inferred kind --
see schema.infer_kind() -- chunk to MAX_CASES_PER_BATCH, one LLM call per
batch, per-batch failure isolation via generate_batches()) -- only the
prompts and output file naming differ. See python.py's docstring, and
llm/prompts/system_guardrails.md for the trust-model rules shared across
every runtime.
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
    "endpoint": "node_jest_endpoint.md",
    "function": "node_jest_function.md",
}


class NodeGenerator(Generator):
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
                label=f"node:{kind}",
            )
            generated.extend(files)
            errors.extend(batch_errors)
        return generated, errors

    def _generate_batch(self, cases: list[TestCase], kind: str, batch_index: int) -> GeneratedFile:
        user_prompt = self._build_user_prompt(cases, _KIND_TO_PROMPT[kind])
        raw = generate_structured(self._system_prompt, user_prompt, GENERATED_FILE_SCHEMA)
        output = parse_generated_file(raw)
        file_path = f"node/test_{kind}_batch{batch_index}.test.js"
        return assemble_generated_file(output, cases, file_path=file_path, runner="jest")

    def _build_user_prompt(self, cases: list[TestCase], prompt_template: str) -> str:
        instructions = load_prompt(prompt_template)
        cases_json = [case_to_prompt_dict(c) for c in cases]
        return (
            f"{instructions}\n\n"
            f"Generate Jest test functions for these test cases "
            f"(JSON array, one entry per case):\n\n{json.dumps(cases_json, indent=2)}"
        )
