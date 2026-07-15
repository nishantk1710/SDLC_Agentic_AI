"""
frontend_spec_agent.py
======================

An Agent (graph node) that turns extracted product specifications into three
frontend deliverables using the Anthropic LLM.

INPUTS  (all read from $SHARED_DIR):
    - extracted_requirements.json
    - user_features.json
    - glossary.json
    - db_schema.json

OUTPUTS (all written to $SHARED_DIR):
    - routes.json            (B2  Route List)      page name -> path (params included)
    - state_transitions.md   (B3  State Transition) per-page Loading/Empty/Error/Success
    - tokens.json            (C6  Design Tokens)    color / spacing / radius / typography

Derivation rules:
    - tokens.json           <- extracted_requirements.json (ui token source / ui tokens)
                               (DB schema is intentionally NOT used here — design tokens
                                are a styling concern, unrelated to the data model.)
    - routes.json           <- all four docs (functional, non-functional, business
                               rules, constraints, external interfaces, user features,
                               and the DB schema's entities/relationships)
    - state_transitions.md  <- all four docs (same sources as routes)

Two ways to run:
    1. As a node in an agentic flow:
           from frontend_spec_agent import FrontendSpecAgent
           agent = FrontendSpecAgent()
           new_state = agent.run(state)        # or agent(state)  -- LangGraph style

    2. Standalone (runs only this functionality end to end):
           python frontend_spec_agent.py
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from anthropic import AnthropicFoundry
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
load_dotenv()  # must run before we read env vars / construct the client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("frontend_spec_agent")

# Model is configurable so you never have to touch code to swap it.
# NOTE: on Azure Foundry this must be your DEPLOYMENT NAME, not the public model id.
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL") or "claude-sonnet-5"

# Foundry endpoint (full base URL, e.g. https://<resource>.services.ai.azure.com/anthropic)
ANTHROPIC_ENDPOINT = os.getenv("ANTHROPIC_ENDPOINT") or None

# int() on an empty string throws, so fall back when the env value is blank.
MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS") or "8000")

# Input / output filenames
INPUT_FILES = {
    "requirements": "extracted_requirements.json",
    "user_features": "user_features.json",
    "glossary": "glossary.json",
    "db_schema": "db_schema.json",
}
OUTPUT_FILES = {
    "routes": "routes.json",
    "state_transitions": "state_transitions.md",
    "tokens": "tokens.json",
}


# --------------------------------------------------------------------------- #
# Small I/O + parsing helpers
# --------------------------------------------------------------------------- #
def _resolve_shared_dir(shared_dir: Optional[str | os.PathLike] = None) -> Path:
    """Return the SHARED_DIR path, preferring an explicit arg over the env var."""
    raw = shared_dir or os.getenv("SHARED_DIR")
    if not raw:
        raise EnvironmentError(
            "SHARED_DIR is not set. Add it to your .env "
            "(e.g. SHARED_DIR=/path/to/shared) or pass it to FrontendSpecAgent."
        )
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"SHARED_DIR does not exist: {path}")
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    logger.info("Wrote %s", path)


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")
    logger.info("Wrote %s", path)


def _extract_json(text: str) -> Any:
    """
    Pull a JSON object out of an LLM response, tolerating ```json fences or
    stray preamble. Raises ValueError if nothing parseable is found.
    """
    cleaned = text.strip()

    # Strip a fenced ```json ... ``` block if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} span.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise ValueError(f"Could not parse JSON from model output:\n{text[:500]}")


def _extract_markdown(text: str) -> str:
    """Strip a wrapping ```markdown fence if the model added one."""
    fence = re.search(r"```(?:markdown|md)?\s*(.*?)```", text.strip(), re.DOTALL)
    return (fence.group(1) if fence else text).strip()


# --------------------------------------------------------------------------- #
# The Agent
# --------------------------------------------------------------------------- #
class FrontendSpecAgent:
    """
    Generates the frontend Route List, State Transitions, and Design Tokens.

    Usable both as a standalone processor and as a node in an agentic graph.
    In a graph, `run(state)` reads inputs from SHARED_DIR (or from `state` if
    the loaded docs are already present) and returns a state update containing
    the generated artifacts and their file paths.
    """

    def __init__(
        self,
        shared_dir: Optional[str | os.PathLike] = None,
        model: str = DEFAULT_MODEL,
        client: Optional[AnthropicFoundry] = None,
    ) -> None:
        self.shared_dir = _resolve_shared_dir(shared_dir)
        self.model = model
        self.client = client or self._build_client()

    @staticmethod
    def _build_client() -> AnthropicFoundry:
        """
        Build an Azure AI Foundry client from environment variables.
        Fails fast with a clear message if credentials are missing, instead
        of leaking a confusing 401 from the server later.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is empty. Set it in .env to your Azure "
                "Foundry key (the 'Key' value from your Claude deployment's "
                "Details tab)."
            )
        if not ANTHROPIC_ENDPOINT:
            raise EnvironmentError(
                "ANTHROPIC_ENDPOINT is empty. Set it to your Foundry base URL, "
                "e.g. https://<resource>.services.ai.azure.com/anthropic"
            )
        return AnthropicFoundry(api_key=api_key, base_url=ANTHROPIC_ENDPOINT)

    # -- LLM plumbing ------------------------------------------------------- #
    def _complete(self, system: str, user: str) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )

    def _complete_json(self, system: str, user: str, retries: int = 1) -> Any:
        """Call the model and parse JSON, retrying once with a stricter nudge."""
        last_err: Optional[Exception] = None
        for attempt in range(retries + 1):
            raw = self._complete(system, user)
            try:
                return _extract_json(raw)
            except ValueError as err:
                last_err = err
                logger.warning("JSON parse failed (attempt %d): %s", attempt + 1, err)
                user = (
                    user
                    + "\n\nIMPORTANT: Return ONLY valid JSON. No prose, no markdown, "
                    "no code fences."
                )
        raise RuntimeError(f"Model did not return valid JSON: {last_err}")

    # -- Input loading ------------------------------------------------------ #
    def _load_inputs(self, state: Optional[dict] = None) -> dict[str, Any]:
        """
        Load the four input docs. If a graph passed them in `state`, reuse
        those; otherwise read them from SHARED_DIR.
        """
        state = state or {}
        inputs: dict[str, Any] = {}
        for key, filename in INPUT_FILES.items():
            if key in state and state[key] is not None:
                inputs[key] = state[key]
            else:
                inputs[key] = _read_json(self.shared_dir / filename)
        return inputs

    # -- Artifact generators ----------------------------------------------- #
    def generate_tokens(self, requirements: Any) -> dict:
        """
        Design Tokens (C6) from extracted_requirements only.

        The DB schema is deliberately excluded: tokens describe visual styling
        (color/spacing/radius/typography) and have no relationship to the data
        model, so including the schema would only dilute the prompt.
        """
        system = (
            "You are a senior design-systems engineer. From the product's UI "
            "token source in the extracted requirements, produce a COMPLETE design "
            "token set. Include color, spacing, radius, and typography (font) — not "
            "color alone. Use real values (hex, px, font specs), never screenshots. "
            "Return ONLY a JSON object with top-level keys: color, spacing, radius, "
            "font. Fill sensible, consistent defaults where the requirements are "
            "silent. No prose, no code fences."
        )
        user = (
            "Extracted requirements (use the ui token source / ui tokens fields as "
            "the primary basis):\n"
            f"{json.dumps(requirements, indent=2, ensure_ascii=False)}"
        )
        return self._complete_json(system, user)

    def generate_routes(self, inputs: dict[str, Any]) -> dict:
        """Route List (B2) from all four docs."""
        system = (
            "You are a frontend architect. Derive the complete frontend route map "
            "for the application. Consider functional and non-functional requirements, "
            "business rules, constraints, external interfaces, user features, and the "
            "DB schema (its entities and relationships strongly imply the list/detail "
            "pages the UI needs — e.g. an Order entity implies order list and order "
            "detail routes). Output every page the app needs and its path, including "
            "path params (e.g. '/products/:id'). Keys are human-readable page names, "
            "values are route paths. Return ONLY a flat JSON object mapping page name "
            "-> path. No prose, no code fences."
        )
        user = self._build_full_context(inputs)
        return self._complete_json(system, user)

    def generate_state_transitions(self, inputs: dict[str, Any]) -> str:
        """State Transitions (B3) from all four docs — Markdown output."""
        system = (
            "You are a frontend architect writing an implementation spec. For EACH "
            "frontend page, document the WITHIN-PAGE UI states so a developer never "
            "has to guess: Loading, Empty, Error, and Success. These are per-page UI "
            "states, NOT page-to-page navigation. Base pages and states on the "
            "functional/non-functional requirements, business rules, constraints, "
            "external interfaces, user features, and the DB schema (use entities and "
            "their relationships to decide which pages are data-backed and therefore "
            "need Loading/Empty/Error states).\n\n"
            "Return Markdown only. Use this shape per page:\n\n"
            "<Page Name>:\n"
            "- Loading → <what shows>\n"
            "- Empty   → <what shows>\n"
            "- Error   → <what shows>\n"
            "- Success → <what shows>\n\n"
            "Separate pages with a blank line. No preamble, no code fences."
        )
        user = self._build_full_context(inputs)
        raw = self._complete(system, user)
        return _extract_markdown(raw)

    @staticmethod
    def _build_full_context(inputs: dict[str, Any]) -> str:
        return (
            "=== extracted_requirements.json ===\n"
            f"{json.dumps(inputs['requirements'], indent=2, ensure_ascii=False)}\n\n"
            "=== user_features.json ===\n"
            f"{json.dumps(inputs['user_features'], indent=2, ensure_ascii=False)}\n\n"
            "=== glossary.json ===\n"
            f"{json.dumps(inputs['glossary'], indent=2, ensure_ascii=False)}\n\n"
            "=== db_schema.json ===\n"
            f"{json.dumps(inputs['db_schema'], indent=2, ensure_ascii=False)}"
        )

    # -- Orchestration ------------------------------------------------------ #
    def run(self, state: Optional[dict] = None) -> dict:
        """
        Execute the full node. Returns a state update dict:
            {
              "routes": {...},
              "state_transitions": "<markdown>",
              "tokens": {...},
              "output_paths": {"routes": "...", "state_transitions": "...", "tokens": "..."},
            }
        """
        logger.info("FrontendSpecAgent starting (SHARED_DIR=%s, model=%s)",
                    self.shared_dir, self.model)

        inputs = self._load_inputs(state)

        logger.info("Generating design tokens...")
        tokens = self.generate_tokens(inputs["requirements"])

        logger.info("Generating route list...")
        routes = self.generate_routes(inputs)

        logger.info("Generating state transitions...")
        state_transitions = self.generate_state_transitions(inputs)

        # Persist to SHARED_DIR
        tokens_path = self.shared_dir / OUTPUT_FILES["tokens"]
        routes_path = self.shared_dir / OUTPUT_FILES["routes"]
        transitions_path = self.shared_dir / OUTPUT_FILES["state_transitions"]

        _write_json(tokens_path, tokens)
        _write_json(routes_path, routes)
        _write_text(transitions_path, state_transitions)

        logger.info("FrontendSpecAgent finished.")

        # Merge into incoming state so downstream nodes see everything.
        result = {
            "routes": routes,
            "state_transitions": state_transitions,
            "tokens": tokens,
            "output_paths": {
                "routes": str(routes_path),
                "state_transitions": str(transitions_path),
                "tokens": str(tokens_path),
            },
        }
        if state:
            return {**state, **result}
        return result

    # LangGraph-style callable node: node(state) -> state_update
    def __call__(self, state: Optional[dict] = None) -> dict:
        return self.run(state)


# --------------------------------------------------------------------------- #
# Standalone entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    agent = FrontendSpecAgent()
    result = agent.run()
    print("\nDone. Generated files:")
    for name, path in result["output_paths"].items():
        print(f"  - {name:18s} {path}")


if __name__ == "__main__":
    main()