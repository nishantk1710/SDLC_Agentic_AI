"""
frontend_structure_agent.py
===========================

An Agent (graph node) that produces the agreed frontend project/folder layout
that all generated frontend code must follow, using the Anthropic LLM via
Azure AI Foundry.

INPUTS  (all read from $SHARED_DIR):
    - extracted_requirements.json
    - user_features.json
    - routes.json                (the Route List from the earlier node)

OUTPUT (written to $SHARED_DIR):
    - frontend-structure.json    (E4  Project Structure — frontend)
      A nested object describing the folder tree; leaf values are short
      descriptions of what each folder/file holds.

Two ways to run:
    1. As a node in an agentic flow:
           from frontend_structure_agent import FrontendStructureAgent
           agent = FrontendStructureAgent()
           new_state = agent.run(state)        # or agent(state)  -- LangGraph style

    2. Standalone (runs only this functionality end to end):
           python frontend_structure_agent.py
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
logger = logging.getLogger("frontend_structure_agent")

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
    "routes": "routes.json",
}
OUTPUT_FILES = {
    "structure": "frontend-structure.json",
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
            "(e.g. SHARED_DIR=/path/to/shared) or pass it to FrontendStructureAgent."
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


def _extract_json(text: str) -> Any:
    """
    Pull a JSON object out of an LLM response, tolerating ```json fences or
    stray preamble. Raises ValueError if nothing parseable is found.
    """
    cleaned = text.strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise ValueError(f"Could not parse JSON from model output:\n{text[:500]}")


# --------------------------------------------------------------------------- #
# The Agent
# --------------------------------------------------------------------------- #
class FrontendStructureAgent:
    """
    Generates the frontend project structure (E4).

    Usable both as a standalone processor and as a node in an agentic graph.
    In a graph, `run(state)` reads inputs from SHARED_DIR (or from `state` if
    the loaded docs are already present) and returns a state update containing
    the generated structure and its file path.
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
        """Build an Azure AI Foundry client from env vars, failing fast if unset."""
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
        Load the three input docs. If a graph passed them in `state`, reuse
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

    # -- Artifact generator ------------------------------------------------- #
    def generate_structure(self, inputs: dict[str, Any]) -> dict:
        """Frontend project structure (E4) from requirements, features, and routes."""
        system = (
            "You are a senior frontend architect. Produce the agreed frontend "
            "PROJECT/FOLDER STRUCTURE that all generated frontend code must follow. "
            "Base the layout on the technology and constraints in the requirements, "
            "the pages implied by the route list, and the user features.\n\n"
            "Rules:\n"
            "- Return ONLY a single JSON object representing a nested folder tree.\n"
            "- A folder is an object whose keys end with '/'. Its value is either a "
            "nested object (subfolders/files) or a short string describing its purpose.\n"
            "- A file is a key WITHOUT a trailing '/', with a short string description "
            "as its value.\n"
            "- Include the standard frontend directories (e.g. components, pages, "
            "services, hooks, utils, types) plus any folders the routes/features clearly "
            "require. Keep it realistic and not over-engineered.\n"
            "- Do NOT include prose, comments, markdown, or code fences — JSON only."
        )
        user = self._build_full_context(inputs)
        return self._complete_json(system, user)

    @staticmethod
    def _build_full_context(inputs: dict[str, Any]) -> str:
        return (
            "=== extracted_requirements.json ===\n"
            f"{json.dumps(inputs['requirements'], indent=2, ensure_ascii=False)}\n\n"
            "=== user_features.json ===\n"
            f"{json.dumps(inputs['user_features'], indent=2, ensure_ascii=False)}\n\n"
            "=== routes.json (Route List) ===\n"
            f"{json.dumps(inputs['routes'], indent=2, ensure_ascii=False)}"
        )

    # -- Orchestration ------------------------------------------------------ #
    def run(self, state: Optional[dict] = None) -> dict:
        """
        Execute the full node. Returns a state update dict:
            {
              "frontend_structure": {...},
              "output_paths": {"frontend_structure": "..."},
            }
        """
        logger.info("FrontendStructureAgent starting (SHARED_DIR=%s, model=%s)",
                    self.shared_dir, self.model)

        inputs = self._load_inputs(state)

        logger.info("Generating frontend project structure...")
        structure = self.generate_structure(inputs)

        structure_path = self.shared_dir / OUTPUT_FILES["structure"]
        _write_json(structure_path, structure)

        logger.info("FrontendStructureAgent finished.")

        result = {
            "frontend_structure": structure,
            "output_paths": {"frontend_structure": str(structure_path)},
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
    agent = FrontendStructureAgent()
    result = agent.run()
    print("\nDone. Generated files:")
    for name, path in result["output_paths"].items():
        print(f"  - {name:20s} {path}")


if __name__ == "__main__":
    main()