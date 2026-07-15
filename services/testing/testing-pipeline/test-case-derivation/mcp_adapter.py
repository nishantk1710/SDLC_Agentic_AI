"""ZenseAI MCP test-case tool adapter for Stage B.

Conforms to the blueprint (MCP_TOOL_BLUEPRINT.md): the real ZenseAI tool is a
**FastMCP** server whose Python tool (`call_python_test_case_generation_genie`,
blueprint §4.1) takes ``(user_input, bearer_token, api_id)`` and returns
``{stepInformation, fileContents{...}}`` with the generated pytest files inside
``fileContents`` (blueprint §4.2). This adapter therefore:

  * speaks the **MCP protocol** via a lazily-imported ``fastmcp.Client`` (not REST),
  * is **Python-only** (``supports(profile)`` — the genie is a Python test genie;
    other stacks use the LLM fallback — decision: "MCP = capability of the Python
    handler, never the global default"),
  * builds the tool's ``user_input`` from the pipeline data,
  * **normalizes the genie's test *code* into Stage B ``test_cases``** (decision 1:
    one case per generated file, ``type="generated"``, code carried in ``expected``).

POC status: with ``TESTING_MCP_URL`` unset, ``is_available()`` is False and the
router uses the direct-LLM fallback. Wire it by setting ``TESTING_MCP_URL`` /
``TESTING_MCP_API_KEY`` / ``TESTING_MCP_API_ID`` (see ACCESS_NEEDED.md).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

from stack_detector import StackProfile
from tcd_config import MCPSettings, mcp_settings

logger = logging.getLogger(__name__)


class MCPUnavailable(RuntimeError):
    """Raised when the MCP tool is not configured/reachable/usable."""


# ---------------------------------------------------------------------------
# capability checks
# ---------------------------------------------------------------------------
def is_available(cfg: MCPSettings = mcp_settings) -> bool:
    """True only if an MCP endpoint is configured (``TESTING_MCP_URL`` set)."""
    return cfg.is_available


def supports(profile: StackProfile, cfg: MCPSettings = mcp_settings) -> bool:
    """Whether the MCP genie can serve this stack. The ZenseAI tool is Python
    only, so non-Python stacks are left to the LLM fallback."""
    return bool(profile) and profile.language in cfg.supported_languages


def health(cfg: MCPSettings = mcp_settings) -> bool:
    """Reachable AND exposes the configured tool. False (with a warning) on any
    failure so the router treats it as 'use the fallback'."""
    if not cfg.is_available:
        return False
    try:
        return _run(_ahealth(cfg))
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("MCP health check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------
def generate_test_cases(
    requirements: List[Dict[str, Any]],
    mapping_tree: Dict[str, Any],
    strategy: Dict[str, Any],
    cfg: MCPSettings = mcp_settings,
) -> List[Dict[str, Any]]:
    """Call the ZenseAI MCP tool and normalize its output into ``test_cases``.

    The router only calls this after ``is_available`` + ``health`` + ``supports``,
    but we re-validate config here and raise ``MCPUnavailable`` on any gap so the
    router's ``except`` cleanly triggers the LLM fallback.
    """
    if not cfg.is_available:
        raise MCPUnavailable("ZenseAI MCP tool is not configured (TESTING_MCP_URL unset).")
    if cfg.api_id is None:
        raise MCPUnavailable("TESTING_MCP_API_ID not set (required by the ZenseAI tool).")

    user_input = build_user_input(requirements, mapping_tree, strategy)
    payload = _run(_acall_tool(cfg, user_input))
    cases = normalize_response(payload)
    logger.info("MCP genie returned %d generated test file(s) -> cases", len(cases))
    return cases


def build_user_input(
    requirements: List[Dict[str, Any]],
    mapping_tree: Dict[str, Any],
    strategy: Dict[str, Any],
) -> str:
    """Build the single ``user_input`` string the genie expects.

    The genie is an LLM agent that accepts a JSON description of the app + what
    to test. We hand it requirements, symbol signatures, and the strategy. (Exact
    optimal shape is an open question for ZenseAI — see ACCESS_NEEDED.md.)
    """
    symbols = [
        {"id": sid, "signature": node.get("signature") or node.get("symbol_type")}
        for sid, node in (mapping_tree or {}).get("symbols", {}).items()
    ]
    return json.dumps(
        {
            "instruction": (
                "Generate a comprehensive test suite (target >=90% coverage) for the "
                "application described below. Return only JSON per your output contract."
            ),
            "requirements": requirements,
            "symbols": symbols,
            "strategy": strategy,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# response normalization (genie test *code* -> Stage B test_cases)
# ---------------------------------------------------------------------------
def normalize_response(payload: Any) -> List[Dict[str, Any]]:
    """Map the genie's ``{stepInformation, fileContents}`` (with ``{"tests":[...]}``
    inside) into Stage B ``test_cases`` — one ``type="generated"`` case per file.

    Requirement linkage is not provided by the genie, so ``req_id`` is left empty
    (the orchestrator flags these); the generated code is carried in ``expected``
    so Stage C can consume it. Returns [] if no generated files are found (the
    router then falls back to the LLM)."""
    files = _find_generated_tests(payload)
    cases: List[Dict[str, Any]] = []
    for i, f in enumerate(files, start=1):
        path = f.get("path") or f"generated_test_{i}.py"
        content = f.get("content", "")
        cases.append(
            {
                "id": f"TC-GEN-{i}",
                "req_id": "",  # genie output is not requirement-traced
                "type": "generated",
                "input": {"path": path},
                "expected": {"test_file": content},
                "notes": f"Generated by the ZenseAI MCP test genie (file: {path}).",
                "target_symbols": [],
            }
        )
    return cases


def _find_generated_tests(payload: Any) -> List[Dict[str, Any]]:
    """Locate the genie's ``[{"path","content"}]`` list within its response."""
    # already the contract shape?
    if isinstance(payload, dict) and isinstance(payload.get("tests"), list):
        return [t for t in payload["tests"] if isinstance(t, dict)]

    # nested under fileContents: scan each step's combined text for a tests JSON
    if isinstance(payload, dict) and isinstance(payload.get("fileContents"), dict):
        for text in payload["fileContents"].values():
            found = _tests_from_text(text)
            if found:
                return found

    # a raw string payload
    if isinstance(payload, str):
        return _tests_from_text(payload)

    return []


def _tests_from_text(text: Any) -> List[Dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return []
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and isinstance(data.get("tests"), list):
        return [t for t in data["tests"] if isinstance(t, dict)]
    if isinstance(data, list) and all(isinstance(t, dict) for t in data):
        return data
    return []


# ---------------------------------------------------------------------------
# MCP transport (fastmcp.Client, lazily imported)
# ---------------------------------------------------------------------------
async def _ahealth(cfg: MCPSettings) -> bool:
    from fastmcp import Client  # lazy import

    async with Client(cfg.url) as client:
        tools = await client.list_tools()
        names = {getattr(t, "name", None) for t in tools}
        if cfg.tool_name in names:
            return True
        logger.warning("MCP reachable but tool %r not listed (found: %s)", cfg.tool_name, names)
        return False


async def _acall_tool(cfg: MCPSettings, user_input: str) -> Any:
    from fastmcp import Client  # lazy import

    args = {"user_input": user_input, "bearer_token": cfg.api_key or "", "api_id": cfg.api_id}
    async with Client(cfg.url) as client:
        result = await client.call_tool(cfg.tool_name, args)
    return _extract_payload(result)


def _extract_payload(result: Any) -> Any:
    """Pull the tool's return value out of a fastmcp CallToolResult, tolerant of
    version differences (.data / .structured_content / text content block)."""
    for attr in ("data", "structured_content", "structuredContent"):
        val = getattr(result, attr, None)
        if val:
            return val
    content = getattr(result, "content", None)
    if content:
        block = content[0]
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return result


def _run(coro):
    """Run an async coroutine from sync code, even if a loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # a loop is already running (e.g. inside async server) -> run on a worker thread
    import threading

    box: Dict[str, Any] = {}

    def _worker() -> None:
        box["value"] = asyncio.run(coro)

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    return box.get("value")
