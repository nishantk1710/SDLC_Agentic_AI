"""Routing for Stage B: ZenseAI MCP genie if it fits the stack + is healthy,
otherwise the stack-parameterized direct-LLM planner.

Both paths return the SAME normalized ``test_cases`` shape. Order (reference §5):

    detect stack -> select handler
    cache hit ? -> return cached
    handler is MCP-capable AND MCP supports this stack AND available AND healthy
        -> MCP genie (on ANY failure, fall back)
    else / empty result -> direct-LLM planner (stack-parameterized)

Key rule (decision): MCP is a *capability of the Python handler*, never the
global default. Non-Python stacks (and Python when MCP is down) use the LLM
fallback, which produces fully requirement-traced cases for any stack.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import mcp_adapter
import tcd_cache
from direct_planner import plan_test_cases as _direct_plan
from generation_handlers import select_handler
from stack_detector import detect_stack
from tcd_llm_client import LLMCallable

logger = logging.getLogger(__name__)


def derive_test_cases(
    requirements: List[Dict[str, Any]],
    mapping_tree: Dict[str, Any],
    strategy: Dict[str, Any],
    tech_stack: Optional[Dict[str, Any]] = None,
    llm: Optional[LLMCallable] = None,
    use_cache: bool = True,
) -> Tuple[List[Dict[str, Any]], str]:
    """Return ``(test_cases, source)`` where source is 'cache'|'mcp'|'direct_llm'."""
    profile = detect_stack(tech_stack, mapping_tree, requirements)
    handler = select_handler(profile)

    key = tcd_cache.cache_key(requirements, mapping_tree, strategy, profile.key)
    if use_cache:
        cached = tcd_cache.get(key)
        if cached is not None:
            return cached, "cache"

    cases: List[Dict[str, Any]] = []
    source = "direct_llm"

    mcp_eligible = (
        handler.mcp_capable
        and mcp_adapter.is_available()
        and mcp_adapter.supports(profile)
    )
    if mcp_eligible and mcp_adapter.health():
        try:
            cases = mcp_adapter.generate_test_cases(requirements, mapping_tree, strategy)
            source = "mcp"
            logger.info("Stage B: used ZenseAI MCP genie for %s (%d cases)", profile.describe(), len(cases))
        except Exception as exc:
            logger.warning("Stage B: MCP path failed (%s); falling back to direct LLM", exc)
            cases = []
    elif handler.mcp_capable and mcp_adapter.is_available():
        # MCP configured but not usable for this run (unhealthy / stack unsupported)
        logger.info("Stage B: MCP not usable for %s; using direct LLM", profile.describe())

    if not cases:
        cases = _direct_plan(requirements, mapping_tree, strategy, profile=profile, llm=llm)
        source = "direct_llm"

    if use_cache and cases:
        tcd_cache.put(key, cases)

    return cases, source
