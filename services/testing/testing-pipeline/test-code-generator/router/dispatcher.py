"""
dispatcher.py — Step C's entry point.

Loads test_cases.json, resolves the project's tech stack, and routes each
case to a generator by ROLE, not by a single project-wide tech_stack:

  - type == "e2e_flow"           -> the "e2e" generator (Playwright), always,
                                     regardless of backend tech_stack
  - target_symbols resolve to a  -> the "react" generator, always, regardless
    frontend language in Chunks     of backend tech_stack
  - anything else                -> the backend generator for the resolved
                                     tech_stack ("python", "node", ...), via
                                     schema.infer_kind() to decide endpoint
                                     vs function within that generator

Schema v2 note: the real Step B output has no target.kind field anymore
(no endpoint/function/component label at all -- see schema.py's
infer_kind()). Component detection is grounded in Chunks instead (see
tech_stack.build_symbol_language_index()/symbol_language()): a chunk's
symbol_id matches target_symbols verbatim and carries the real language,
which is a strictly better signal than guessing from a filename
extension. If Chunks isn't available or a symbol isn't in it,
symbol_language() returns None and the case falls through to normal
e2e/backend routing -- graceful, not a hard failure.

This matters for real (likely polyglot) projects: a FastAPI+React project
has both endpoint/function cases (Python) and component cases (React) in
the same test_cases.json -- confirmed on the real QuickBite Chunks data,
which includes a genuine React frontend alongside the Python backend.
Routing everything through one resolved backend tech_stack would send
React cases to the Python generator (or vice versa) and crash the whole
run on the first unsupported case.

A routing key with no registered generator (e.g. "react" before that
generator exists) does NOT fail the whole run -- it's recorded as a
generation error and the run continues with whatever groups DO have a
registered generator. See dispatch()'s return value.
"""

import logging
from collections import defaultdict
from pathlib import Path

from codegen.base_generator import GeneratedFile, Generator
from schema import TestCase, load_test_cases
from tech_stack import (
    CHUNKS_DIR,
    DESIGN_TO_IMPLEMENTATION_DIR,
    build_symbol_language_index,
    resolve_tech_stack,
    symbol_language,
)

logger = logging.getLogger(__name__)

_GENERATOR_REGISTRY: dict[str, Generator] = {}

_FRONTEND_LANGUAGES = {"javascript", "typescript"}


def register_generator(key: str, generator: Generator) -> None:
    """Registers a Generator under a routing key -- a tech_stack value
    ("python", "node", "express") for endpoint/function cases, or the fixed
    keys "react" / "e2e" for component / e2e_flow cases respectively."""
    _GENERATOR_REGISTRY[key] = generator


def group_by_req_id(cases: list[TestCase]) -> dict[str, list[TestCase]]:
    groups: dict[str, list[TestCase]] = defaultdict(list)
    for case in cases:
        groups[case.req_id].append(case)
    return dict(groups)


def routing_key_for(case: TestCase, tech_stack: str, symbol_language_index: dict[str, str]) -> str:
    """Which registry key a case's generator should be looked up under.
    Endpoint vs function is no longer a field to read (schema v2 dropped
    target.kind) -- it's inferred per-case by the generator itself via
    schema.infer_kind(). Component detection is grounded in Chunks: if any
    of the case's target_symbols resolves to a frontend language, route to
    "react" unconditionally, before considering e2e_flow or backend
    tech_stack -- a case can't simultaneously target real frontend code and
    need the backend generator."""
    language = symbol_language(case.target_symbols, symbol_language_index)
    if language in _FRONTEND_LANGUAGES:
        return "react"
    if case.type == "e2e_flow":
        return "e2e"
    return tech_stack


def dispatch(
    test_cases_path: str,
    contracts_dir: Path = DESIGN_TO_IMPLEMENTATION_DIR,
    chunks_dir: Path = CHUNKS_DIR,
) -> tuple[list[GeneratedFile], list[str]]:
    """Load test_cases.json, resolve tech stack, group cases by routing key,
    and run each group through its registered generator. Returns
    (generated_files, generation_errors) -- a group with no registered
    generator, or whose generator raises, is recorded as an error and
    skipped rather than failing every other group."""
    test_case_file = load_test_cases(test_cases_path)
    tech_stack = resolve_tech_stack(contracts_dir, chunks_dir)
    symbol_language_index = build_symbol_language_index(chunks_dir)

    by_routing_key: dict[str, list[TestCase]] = defaultdict(list)
    for case in test_case_file.test_cases:
        by_routing_key[routing_key_for(case, tech_stack, symbol_language_index)].append(case)

    logger.info(
        "dispatching %d case(s) across routing keys %s (tech_stack=%r)",
        len(test_case_file.test_cases), list(by_routing_key), tech_stack,
    )

    generated: list[GeneratedFile] = []
    errors: list[str] = []

    for key, cases in by_routing_key.items():
        generator = _GENERATOR_REGISTRY.get(key)
        if generator is None:
            msg = f"no generator registered for routing key {key!r}; {len(cases)} case(s) skipped"
            logger.warning(msg)
            errors.append(msg)
            continue
        try:
            files, generator_errors = generator.generate(cases)
            generated.extend(files)
            errors.extend(generator_errors)
        except NotImplementedError as e:
            # A stub with no implementation at all -- the whole routing-key
            # group is skipped. A real generator instead returns per-batch
            # errors via generator_errors above, so one bad batch doesn't
            # take the rest of that generator's output down with it.
            msg = f"routing key {key!r}: {e} ({len(cases)} case(s) skipped)"
            logger.warning(msg)
            errors.append(msg)

    return generated, errors
