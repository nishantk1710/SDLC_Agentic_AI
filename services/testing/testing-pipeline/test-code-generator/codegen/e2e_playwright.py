"""
e2e_playwright.py — stub. Playwright/Chromium E2E generation (reference doc
§10: "e2e (any stack, D2) -> codegen/e2e_playwright.py") is Phase 6 in the
build order (§11).

Routing is already correct: router/dispatcher.py's routing_key_for() sends
every `type == "e2e_flow"` case here regardless of the project's backend
tech_stack (a Python or Node project can both have e2e_flow cases). What's
still missing is only the generation logic itself, not the routing.
"""

from codegen.base_generator import GeneratedFile, Generator
from schema import TestCase


class E2EPlaywrightGenerator(Generator):
    def generate(self, cases: list[TestCase]) -> tuple[list[GeneratedFile], list[str]]:
        raise NotImplementedError(
            "Phase 6 (Polyglot) -- Playwright/Chromium E2E generation isn't implemented yet"
        )
