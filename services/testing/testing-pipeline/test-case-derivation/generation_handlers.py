"""Stack-parameterized generation handlers for Stage B (tech-stack agnostic).

Each handler builds the LLM prompt for a family of stacks from a
:class:`StackProfile`. The **generic** handler matches any stack, so an
un-modelled language still gets a reasonable, stack-labelled prompt. The
**Python** handler is the one the ZenseAI MCP genie can back (``mcp_capable``);
it is never the global default — non-Python stacks use their own handler.

Extensible: add a stack by subclassing :class:`BaseHandler` and calling
``register_handler(...)`` — nothing else changes. Selection is first-match over
an ordered registry, generic last.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from stack_detector import StackProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# shared prompt formatting
# ---------------------------------------------------------------------------
def _format_requirements(requirements: List[Dict[str, Any]]) -> str:
    if not requirements:
        return "No requirements provided."
    out = []
    for r in requirements:
        ac = r.get("acceptance_criteria") or []
        ac_str = "".join(f"\n    - {c}" for c in ac) if ac else " (none)"
        out.append(f"{r.get('id', 'REQ-?')}: {r.get('text', '')}\n  acceptance_criteria:{ac_str}")
    return "\n".join(out)


def _format_symbols(mapping_tree: Dict[str, Any], max_symbols: int = 150) -> str:
    symbols = (mapping_tree or {}).get("symbols", {}) or {}
    lines = []
    for i, (sid, node) in enumerate(symbols.items()):
        if i >= max_symbols:
            lines.append(f"... ({len(symbols) - max_symbols} more omitted)")
            break
        sig = node.get("signature") or node.get("symbol_type")
        lines.append(f"- {sid}  signature: {sig}")
    return "\n".join(lines) if lines else "No symbols."


def _format_strategy(strategy: Dict[str, Any]) -> str:
    entries = (strategy or {}).get("test_files_impacted", []) or []
    if not entries:
        return "No strategy entries (derive cases straight from the requirements)."
    lines = []
    for e in entries:
        lines.append(
            f"- {e.get('test_type', '?')} [{e.get('priority', '?')}] "
            f"reqs={e.get('related_requirements', [])} symbols={e.get('target_symbols', [])}\n"
            f"    {e.get('what_needs_testing', '')}"
        )
    return "\n".join(lines)


# The output contract is stack-independent (kept identical across handlers so
# every stack yields the same test_cases schema). Raw string — no str.format.
_OUTPUT_SCHEMA = """OUTPUT: STRICT JSON only, no prose, no markdown:
{
  "test_cases": [
    {
      "id": "TC-003-1",
      "req_id": "REQ-003",
      "type": "happy_path | boundary | invalid_input | error_handling",
      "input": <any JSON>,
      "expected": <any JSON>,
      "notes": "why this case; which acceptance criterion it maps to",
      "target_symbols": ["<symbol_id>", ...]
    }
  ]
}
Use [] for empty arrays."""


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------
class BaseHandler:
    """Generic handler — matches any stack; prompt is parameterized by profile."""

    key = "generic"
    mcp_capable = False  # whether the MCP genie can back this handler (see decision: Python only)

    def matches(self, profile: StackProfile) -> bool:
        return True

    def extra_guidance(self, profile: StackProfile) -> str:
        return ""

    def build_messages(
        self,
        profile: StackProfile,
        requirements: List[Dict[str, Any]],
        mapping_tree: Dict[str, Any],
        strategy: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        extra = self.extra_guidance(profile)
        system = (
            "You derive concrete TEST CASES for an automated testing pipeline.\n\n"
            "TARGET STACK (produce tests idiomatic to THIS stack; do not assume any other):\n"
            f"- language: {profile.language}\n"
            f"- framework: {profile.framework or '(none specified)'}\n"
            f"- kind: {profile.kind}\n"
            f"- test framework: {profile.test_framework or '(language default)'}\n"
            f"- conventions: {profile.conventions}\n\n"
            "You are given REQUIREMENTS (with acceptance criteria), a TEST STRATEGY "
            "(what to test and where), and a CODEBASE MAP (symbols + signatures).\n\n"
            "CRITICAL RULES:\n"
            "- Derive every `expected` value ONLY from the requirements / acceptance "
            "criteria. Use the codebase map solely to shape the `input`. NEVER infer "
            "expected results from how the code appears to behave.\n"
            "- Cover EVERY requirement with at least one case.\n"
            "- Include a mix where sensible: happy_path, boundary, invalid_input, "
            "error_handling. Boundary and negative cases matter most.\n"
            "- `input`/`expected` are JSON values whose shape fits the target symbol's "
            "signature AND the target stack's calling conventions.\n"
            "- `target_symbols` must be ids taken from the CODEBASE MAP.\n"
            '- Give each case a stable id like "TC-<requirement-number>-<n>".\n'
            + (f"\n{extra}\n" if extra else "")
            + "\n" + _OUTPUT_SCHEMA
        )
        user = (
            "REQUIREMENTS:\n" + _format_requirements(requirements) + "\n\n"
            "TEST STRATEGY (what to test / where):\n" + _format_strategy(strategy) + "\n\n"
            "CODEBASE MAP (call shape only):\n" + _format_symbols(mapping_tree) + "\n\n"
            "Derive the test cases as strict JSON per the schema."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]


class FullStackHandler(BaseHandler):
    """Backend + frontend in one repo: generate cases for BOTH tiers, matching
    each case to its target symbol's language. Not MCP-backed (the ZenseAI genie
    is Python-only and cannot cover the frontend)."""

    key = "full_stack"
    mcp_capable = False

    def matches(self, profile: StackProfile) -> bool:
        return bool(profile.full_stack)

    def extra_guidance(self, profile: StackProfile) -> str:
        fe = profile.frontend_framework or "react"
        return (
            f"FULL-STACK APP: a {profile.language} backend AND a {fe} frontend. Generate "
            "cases for BOTH tiers, matching each case to its TARGET SYMBOL's language:\n"
            "  - Backend symbols (e.g. .py): API/Contract cases as {method, path, body} -> "
            "{status_code, json}; pure functions as {args} -> return value or "
            '{"raises": ...}.\n'
            f"  - Frontend symbols (.jsx/.tsx {fe} components/pages): Component cases describing "
            "props / initial state / user interactions -> expected rendered text, roles, or "
            "navigation (React Testing Library style; mock network).\n"
            "  - Include at least one END-TO-END case for the primary user journey, described "
            "as ordered UI steps with expected assertions.\n"
            "Every requirement must get cases in its correct tier: backend requirements -> "
            "backend cases; UI/frontend requirements -> component/E2E cases. Do NOT skip the "
            "frontend."
        )


class PythonHandler(BaseHandler):
    key = "python"
    mcp_capable = True  # the ZenseAI Python test-case genie can back this handler

    def matches(self, profile: StackProfile) -> bool:
        return profile.language == "python"

    def extra_guidance(self, profile: StackProfile) -> str:
        return (
            "STACK NOTES (Python): for plain functions, `input` is the call arguments and "
            "`expected` the return value; represent a raised error as "
            '{"raises": true, "exception": "<ExceptionName>"}. For web endpoints, express '
            "`input` as {method, path, query, body} and `expected` as {status_code, json}."
        )


class NodeHandler(BaseHandler):
    key = "node"

    def matches(self, profile: StackProfile) -> bool:
        return profile.language in ("javascript", "typescript")

    def extra_guidance(self, profile: StackProfile) -> str:
        if profile.framework == "react":
            return (
                "STACK NOTES (React): `input` describes props and/or user interactions; "
                "`expected` describes rendered text/roles/DOM state after render."
            )
        return (
            "STACK NOTES (JS/TS): for functions, `input` is the arguments and `expected` the "
            "return/throw; for HTTP handlers express `input` as {method, path, body} and "
            "`expected` as {status, body}."
        )


# ordered registry; FullStack first (most specific), generic (BaseHandler) last
_REGISTRY: List[BaseHandler] = [FullStackHandler(), PythonHandler(), NodeHandler(), BaseHandler()]


def register_handler(handler: BaseHandler) -> None:
    """Add a handler just before the generic fallback (extensibility hook)."""
    _REGISTRY.insert(len(_REGISTRY) - 1, handler)


def select_handler(profile: StackProfile) -> BaseHandler:
    for h in _REGISTRY:
        if h.matches(profile):
            logger.info("Stage B: selected handler '%s' for stack %s", h.key, profile.describe())
            return h
    return _REGISTRY[-1]


def build_messages(
    profile: StackProfile,
    requirements: List[Dict[str, Any]],
    mapping_tree: Dict[str, Any],
    strategy: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Convenience: select the handler for ``profile`` and build its prompt."""
    return select_handler(profile).build_messages(profile, requirements, mapping_tree, strategy)
