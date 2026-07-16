"""
base_generator.py — the interface every codegen/<runtime>.py module
implements, plus shared helpers so each runtime generator only has to
define its own kind->prompt mapping and file-naming scheme.

The dispatcher only knows about the Generator interface; it never imports
a specific runtime's generator directly. Runtimes register themselves
(see router/dispatcher.py's register_generator()), so unimplemented
runtimes don't block the ones that exist.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel

from llm.structured_output import GeneratedFileOutput
from schema import TestCase

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "llm" / "prompts"

# Tune this to trade off per-call prompt size against total call count.
# Larger batches -> fewer calls -> less repeated system-prompt/instruction
# overhead, but a bigger single prompt, more output tokens needed per call,
# and a bigger single point of failure per call (one bad batch affects more
# cases). Lowered from 12 to 6 after a real run at 12 hit LLM_MAX_TOKENS
# mid-generation on every batch (test_functions came back missing entirely
# -- the model ran out of budget before writing any of it). Shared default;
# a generator may override via its own constructor.
MAX_CASES_PER_BATCH = 6


class AssertionProvenance(BaseModel):
    """Ties one generated assertion's literal value back to the test case
    and `expected` key it must have come from -- what validators/
    traceability_check.py checks against the real test case data."""

    source_case_id: str
    expected_key: str
    expected_value: Any


class GeneratedFile(BaseModel):
    file_path: str
    runner: str  # e.g. "pytest", "jest" — tells Step D how to execute this file
    source_test_case_ids: list[str]
    req_ids: list[str]
    code: str
    provenance: list[AssertionProvenance] = []


class Generator(ABC):
    """Implemented once per routing key (python, node, react, e2e)."""

    @abstractmethod
    def generate(self, cases: list[TestCase]) -> tuple[list[GeneratedFile], list[str]]:
        """Generate test code for the given cases, batched however this
        generator sees fit for LLM call efficiency. Returns (files, errors):
        a batch that fails (LLM error, schema-validation failure on a real
        but malformed response, etc.) is recorded in `errors` and skipped --
        it must NOT lose every other batch in the same call. A stub with no
        real implementation at all may still just raise NotImplementedError
        directly; the dispatcher catches that at the routing-key level."""
        ...


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def case_to_prompt_dict(case: TestCase) -> dict:
    """Only target_symbols/input/expected/notes -- never source code under test."""
    return {
        "id": case.id,
        "req_id": case.req_id,
        "type": case.type,
        "target_symbols": case.target_symbols,
        "input": case.input,
        "expected": case.expected,
        "notes": case.notes,
    }


def chunk(cases: list[TestCase], size: int) -> list[list[TestCase]]:
    return [cases[i : i + size] for i in range(0, len(cases), size)]


def generate_batches(
    batches: list[list[TestCase]],
    generate_one: Callable[[list[TestCase], int], GeneratedFile],
    label: str,
) -> tuple[list[GeneratedFile], list[str]]:
    """Runs generate_one(batch, batch_index) for every batch, isolating
    failures per batch. A single batch failing (LLM call error, a real but
    schema-invalid response, a truncated response, etc.) is recorded in the
    returned errors list and skipped -- it does not lose the other batches'
    results. `label` is just for the error message (e.g. "python:endpoint")."""
    generated: list[GeneratedFile] = []
    errors: list[str] = []
    for batch_index, batch in enumerate(batches):
        try:
            generated.append(generate_one(batch, batch_index))
        except Exception as e:
            case_ids = [c.id for c in batch]
            msg = f"{label} batch {batch_index} ({len(batch)} case(s): {case_ids}): {type(e).__name__}: {e}"
            logger.warning(msg)
            errors.append(msg)
    return generated, errors


def assemble_generated_file(
    output: GeneratedFileOutput, cases: list[TestCase], file_path: str, runner: str
) -> GeneratedFile:
    """Turns the LLM's structured output + the batch's source cases into a
    GeneratedFile. Shared across every runtime generator -- file_path is
    always assigned deterministically by the caller, never trusted from the
    LLM's own output.file_path, since multiple batches could otherwise
    collide on the same name."""
    import_lines = "\n".join(sorted(set(output.imports)))
    function_bodies = "\n\n".join(fn.code for fn in output.test_functions)
    code = f"{import_lines}\n\n\n{function_bodies}\n"

    source_test_case_ids = sorted({
        tc_id for fn in output.test_functions for tc_id in fn.source_test_case_ids
    })
    req_ids = sorted({c.req_id for c in cases})

    provenance = [
        AssertionProvenance(
            source_case_id=entry.source_case_id,
            expected_key=entry.expected_key,
            expected_value=entry.expected_value,
        )
        for fn in output.test_functions
        for entry in fn.expected_value_provenance
    ]

    return GeneratedFile(
        file_path=file_path,
        runner=runner,
        source_test_case_ids=source_test_case_ids,
        req_ids=req_ids,
        code=code,
        provenance=provenance,
    )
