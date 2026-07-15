"""Direct-LLM test-case planner (Stage B primary path / permanent MCP fallback).

Builds its prompt via a stack-aware handler (:mod:`generation_handlers`), so the
tests it asks for are idiomatic to the *detected* stack — never a hardcoded
language. This path is always available; the ZenseAI MCP tool is an additive
alternative behind the router (reference §5). Trust rules (§7) live in the
handler prompt (expected-from-requirements, per-requirement coverage, case types).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from generation_handlers import build_messages
from stack_detector import StackProfile, detect_stack
from tcd_llm_client import LLMCallable, get_default_llm
from test_case_models import parse_test_cases

logger = logging.getLogger(__name__)


def plan_test_cases(
    requirements: List[Dict[str, Any]],
    mapping_tree: Dict[str, Any],
    strategy: Dict[str, Any],
    profile: Optional[StackProfile] = None,
    llm: Optional[LLMCallable] = None,
) -> List[Dict[str, Any]]:
    """Derive test cases via one stack-parameterized LLM call.

    ``profile`` selects the generation handler; when omitted it is detected from
    the mapping tree. Returns ``[]`` on failure so the orchestrator can still
    emit a valid (empty) artifact plus coverage gaps.
    """
    profile = profile or detect_stack(mapping_tree=mapping_tree, requirements=requirements)
    llm = llm or get_default_llm()
    messages = build_messages(profile, requirements, mapping_tree, strategy)
    try:
        raw = llm(messages)
    except Exception as exc:
        logger.error("Stage B direct-LLM planner failed: %s", exc)
        return []
    cases = parse_test_cases(raw)
    logger.info("Stage B direct-LLM planner (%s): %d case(s)", profile.key, len(cases))
    return cases
