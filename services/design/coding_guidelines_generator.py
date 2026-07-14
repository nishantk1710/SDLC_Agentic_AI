#!/usr/bin/env python3
"""
coding_guidelines_generator.py  —  Level-2 Coding Guidelines agent

Consumes the Level-1 artifact (extracted_requirements.json) from the shared
folder and produces the team's coding conventions, framed as an agent skill so
the downstream implementation agent reads them as authoritative convention.

Satisfies E5 (Coding Guidelines) of the design-to-implementation contract.

Reasoning style (mirrors schema_generator.py):
    1. DISTILL   — pull only the guideline-relevant facts from the SRS (tech
       stack, architecture, constraints, security & non-functional rules).
    2. GENERATE  — the model derives concrete, enforceable conventions FOR THIS
       app's stack as structured JSON (grouped rules), so all generated code
       reads as one author.
    3. RENDER    — SKILL.md is rendered *deterministically* from that JSON, so
       the artifact is always well-formed and downstream agents get both a
       machine-readable list and the human-readable skill.

Outputs (written to the shared folder):
    coding_guidelines.json  structured guidelines (categories -> rules)
    skills.md               the SKILL.md-framed artifact, in the §16 format

Two entrypoints, one core:
    • CLI:        python coding_guidelines_generator.py      (uses $SHARED_DIR)
    • LangGraph:  from coding_guidelines_generator import coding_guidelines_node
                  graph.add_node("coding_guidelines", coding_guidelines_node)

Environment:
    SHARED_DIR          folder holding the Level-1 artifacts + where outputs go
    ANTHROPIC_API_KEY   key for the LLM calls (Azure Foundry key)
    ANTHROPIC_ENDPOINT  Foundry base URL, e.g. https://<res>.services.ai.azure.com/anthropic
    DEFAULT_MODEL       model id / deployment name (default 'claude-sonnet-5')
    ANTHROPIC_MAX_TOKENS  cap on generation tokens (default 4000)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coding_guidelines_generator")


def load_dotenv_files() -> None:
    """Load .env if python-dotenv is installed (optional). Real env vars win.
    Called at import time (below) so EVERY os.environ.get() in this module —
    and the Anthropic SDK's own ANTHROPIC_API_KEY lookup — sees the .env values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env", override=False)   # .env next to this script
    load_dotenv(override=False)                  # .env in the current dir, if any


# Load .env BEFORE reading any configuration below.
load_dotenv_files()

# ---------------------------------------------------------------------------
# Config — read from the environment (populated from .env just above)
# ---------------------------------------------------------------------------
ENV_VAR = "SHARED_DIR"
# Model is configurable. On Azure Foundry this is your DEPLOYMENT NAME.
MODEL = os.environ.get("DEFAULT_MODEL") or "claude-sonnet-5"
# Foundry base URL, e.g. https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_ENDPOINT = os.environ.get("ANTHROPIC_ENDPOINT") or None
# int() on an empty string throws, so fall back when the env value is blank.
MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS") or "4000")

IN_REQUIREMENTS = "extracted_requirements.json"

OUT_JSON = "coding_guidelines.json"
OUT_SKILL = "skills.md"

# The E5 artifact header, kept verbatim from the output-artifacts specification
# (§16) so skills.md drops straight into the delivery bundle.
SKILL_HEADER = (
    "## 16. Coding Guidelines\n"
    "**Satisfies:** E5 (Coding Guidelines)\n"
    "**Format:** `SKILL.md` (Markdown) — framed as an agent skill so the "
    "implementation agent reads it as authoritative convention.\n"
    "**Contains:** the team's conventions so all generated code reads as one author.\n"
)


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------
def resolve_shared_dir(cli_dir: str | None) -> Path:
    raw = cli_dir or os.environ.get(ENV_VAR)
    if not raw:
        raise SystemExit(
            f"No location set. Set {ENV_VAR} (the folder with the Level-1 artifacts) "
            f"or pass --dir."
        )
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise SystemExit(f"{ENV_VAR} is not a directory: {p}")
    return p


def load_inputs(shared: Path) -> dict:
    """Read the Level-1 requirements artifact. Fails clearly if missing."""
    f = shared / IN_REQUIREMENTS
    if not f.is_file():
        raise SystemExit(f"Missing Level-1 input: {f}. Run the SRS parser first.")
    return {"extracted_requirements": json.loads(f.read_text(encoding="utf-8"))}


def _texts(items: list) -> list[str]:
    """Flatten a list of requirement objects (or strings) to their text."""
    out: list[str] = []
    for it in items or []:
        if isinstance(it, dict):
            t = it.get("text") or it.get("name") or ""
            if t:
                out.append(str(t))
        elif it:
            out.append(str(it))
    return out


def distill(inputs: dict) -> dict:
    """Pull just the convention-relevant facts, to keep the prompt focused.

    Coding guidelines are driven by the STACK and the cross-cutting rules
    (security, RBAC, architecture) far more than by individual features, so we
    lift tech_stack / constraints / non_functional / business_rules and leave
    the functional catalogue out."""
    er = inputs["extracted_requirements"]
    return {
        "tech_stack": _texts(er.get("tech_stack", [])),
        "constraints": _texts(er.get("constraints", [])),
        "non_functional": _texts(er.get("non_functional", [])),
        "business_rules": _texts(er.get("business_rules", [])),
        "performance": _texts(er.get("performance", [])),
        # A design system implies token-not-hardcoded conventions on the client.
        "has_ui_tokens": bool(er.get("ui_tokens") or er.get("ui_token_source")),
    }


# ---------------------------------------------------------------------------
# LLM plumbing (patchable for testing)
# ---------------------------------------------------------------------------
def _client():
    """Build an Azure AI Foundry client, matching the sibling agents' pattern."""
    try:
        from anthropic import AnthropicFoundry
    except ImportError:
        raise SystemExit("The 'anthropic' package is required. pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is empty. Set it in .env to your Azure Foundry key "
            "(the 'Key' value from your Claude deployment's Details tab)."
        )
    if not ANTHROPIC_ENDPOINT:
        raise SystemExit(
            "ANTHROPIC_ENDPOINT is empty. Set it to your Foundry base URL, e.g. "
            "https://<resource>.services.ai.azure.com/anthropic"
        )
    return AnthropicFoundry(api_key=api_key, base_url=ANTHROPIC_ENDPOINT, timeout=180.0)


def _call_json(system: str, user: str, max_tokens: int = MAX_TOKENS) -> dict:
    """Call the model and parse a JSON object from the reply."""
    resp = _client().messages.create(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    """Robustly extract a JSON object from a model reply."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
GENERATE_SYSTEM = """You are the lead engineer setting the coding conventions for a \
team of AI implementation agents. From an application's technology stack, \
architecture, constraints and non-functional/security requirements, derive the \
team's coding guidelines so that ALL generated code reads as if written by ONE \
author.

These conventions are AUTHORITATIVE: the implementation agent obeys them verbatim. \
So every rule must be:
- CONCRETE and ENFORCEABLE — a reviewer can tell at a glance whether code complies \
(e.g. "Naming: PascalCase components, camelCase vars, kebab-case files"), not vague \
aspirations ("write clean code").
- SPECIFIC TO THIS STACK — name the actual frameworks, libraries and patterns implied \
by the tech stack (e.g. for MERN: functional React components + hooks, Express \
routers/controllers/services layering, Mongoose schemas). Do NOT invent a stack that \
is not implied.
- DERIVED FROM THE REQUIREMENTS — turn security, RBAC, PCI, TLS, rate-limiting, \
design-token and maintainability requirements into code-level rules (e.g. \
"parameterized queries / Mongoose query builders only — never string-concatenated \
queries", "never log or persist raw card data — tokenize via the payment gateway", \
"design-system values come from named tokens, never hard-coded hex/px").
- SHORT — one line each, imperative, no rationale prose.

Group the rules into a small number of categories. Keep the TOTAL to roughly 20-35 \
tight rules across all categories — enough to be a real style guide, not a book.

Respond with STRICT JSON only, no prose, no markdown fences:
{
  "stack_summary": "<one line naming the stack these rules target>",
  "categories": [
    {"name": "<category, e.g. Components & UI>", "rules": ["<rule>", "<rule>"]}
  ],
  "headline_rules": ["<the 5-8 single most important rules, verbatim from above, that capture the house style at a glance>"]
}"""


# ---------------------------------------------------------------------------
# The reasoning step
# ---------------------------------------------------------------------------
def generate_guidelines(inputs: dict) -> dict:
    """Core: distill the SRS -> ask the model for structured conventions."""
    facts = distill(inputs)
    logger.info("Deriving coding guidelines (model=%s)...", MODEL)
    user = (
        "Application facts (from the SRS):\n```json\n"
        + json.dumps(facts, indent=2, ensure_ascii=False)
        + "\n```\nDerive the team's coding guidelines for THIS stack."
    )
    guidelines = _call_json(GENERATE_SYSTEM, user, max_tokens=MAX_TOKENS)
    n = sum(len(c.get("rules", [])) for c in guidelines.get("categories", []))
    logger.info("Guidelines generated: %d rules across %d categories",
                n, len(guidelines.get("categories", [])))
    return guidelines


# ---------------------------------------------------------------------------
# Deterministic rendering (no LLM) — keeps skills.md always well-formed
# ---------------------------------------------------------------------------
def _all_rules(guidelines: dict) -> list[str]:
    rules: list[str] = []
    for cat in guidelines.get("categories", []):
        rules += [str(r).strip() for r in cat.get("rules", []) if str(r).strip()]
    return rules


def render_skill_md(guidelines: dict) -> str:
    """Render the E5 SKILL.md artifact in the §16 output-spec format.

    A flat bullet list of every rule goes inside a ```markdown fence (matching
    the specification's example), preceded by category subheadings so a human
    can scan it. The implementation agent reads the fenced list as convention."""
    headline = [str(r).strip() for r in guidelines.get("headline_rules", []) if str(r).strip()]
    if not headline:
        headline = _all_rules(guidelines)[:8]

    lines = [SKILL_HEADER, "```markdown"]
    # Lead with the headline rules — the at-a-glance house style, matching §16.
    lines += [f"- {r}" for r in headline]
    lines.append("```")
    lines.append("")

    # Full, categorised skill body so the artifact is a complete style guide.
    stack = guidelines.get("stack_summary", "")
    if stack:
        lines.append(f"> Conventions for {stack}. Generated code must read as one author.")
        lines.append("")
    for cat in guidelines.get("categories", []):
        cat_rules = [str(r).strip() for r in cat.get("rules", []) if str(r).strip()]
        if not cat_rules:
            continue
        lines.append(f"### {cat.get('name', 'General')}")
        lines += [f"- {r}" for r in cat_rules]
        lines.append("")

    lines.append("---")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Light deterministic self-validation (warnings only)
# ---------------------------------------------------------------------------
def validate_guidelines(guidelines: dict) -> list[str]:
    warnings: list[str] = []
    rules = _all_rules(guidelines)
    if not rules:
        warnings.append("no rules were produced")
    if len(rules) < 8:
        warnings.append(f"only {len(rules)} rules — the style guide looks thin")
    if not guidelines.get("headline_rules"):
        warnings.append("no headline_rules — skills.md will fall back to the first few rules")
    return warnings


# ---------------------------------------------------------------------------
# Writing outputs
# ---------------------------------------------------------------------------
def write_outputs(shared: Path, guidelines: dict) -> dict:
    paths = {
        "json": shared / OUT_JSON,
        "skill": shared / OUT_SKILL,
    }
    paths["json"].write_text(
        json.dumps(guidelines, indent=2, ensure_ascii=False), encoding="utf-8")
    paths["skill"].write_text(render_skill_md(guidelines), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}


# ---------------------------------------------------------------------------
# Reusable core used by BOTH entrypoints
# ---------------------------------------------------------------------------
def run(shared_dir: str | None = None, inputs: dict | None = None) -> dict:
    """Resolve dir -> load inputs -> generate -> render/write -> return."""
    load_dotenv_files()
    shared = resolve_shared_dir(shared_dir)
    if inputs is None:
        inputs = load_inputs(shared)
    guidelines = generate_guidelines(inputs)
    warnings = validate_guidelines(guidelines)
    paths = write_outputs(shared, guidelines)
    return {"guidelines": guidelines, "warnings": warnings, "paths": paths}


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------
def coding_guidelines_node(state: dict) -> dict:
    """LangGraph node. Reads `shared_dir` (and optional preloaded `inputs`) from
    state; returns the coding-guidelines artifacts to merge back into state.

    Example:
        from langgraph.graph import StateGraph
        graph = StateGraph(dict)
        graph.add_node("coding_guidelines", coding_guidelines_node)
        # state = {"shared_dir": "/path/to/shared"}
    """
    shared_dir = state.get("shared_dir") or state.get("SHARED_DIR")
    inputs = state.get("inputs")  # optional: pass artifacts directly to skip disk read
    result = run(shared_dir=shared_dir, inputs=inputs)
    return {
        "coding_guidelines": result["guidelines"],
        "coding_guidelines_paths": result["paths"],
        "coding_guidelines_warnings": result["warnings"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Generate coding guidelines (SKILL.md) from the Level-1 artifacts")
    ap.add_argument("--dir", default=None,
                    help=f"shared folder (inputs in, outputs out). Overrides ${ENV_VAR}.")
    args = ap.parse_args()

    result = run(shared_dir=args.dir)
    g = result["guidelines"]
    n = sum(len(c.get("rules", [])) for c in g.get("categories", []))
    print(f"Stack: {g.get('stack_summary', '(unspecified)')}")
    print(f"Rules: {n} across {len(g.get('categories', []))} categories "
          f"-> {result['paths'].get('skill')}")
    for w in result["warnings"]:
        print(f"  ⚠ {w}")


if __name__ == "__main__":
    main()
