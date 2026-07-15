"""Tests for Stage B's tech-stack-agnostic layer: detection, handlers, MCP
capability, stack-aware routing, and code->cases normalization. No network/LLM.

Run under pytest, or directly:
    python tests/test_stack_routing.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mcp_adapter  # noqa: E402
import tcd_cache  # noqa: E402
import derivation_router as router  # noqa: E402
from generation_handlers import build_messages, select_handler  # noqa: E402
from stack_detector import detect_stack  # noqa: E402

REQS = [{"id": "REQ-1", "text": "x", "acceptance_criteria": ["a"]}]
MT_EMPTY = {"symbols": {}}


# --- detection ---
def test_detection_sources():
    assert detect_stack({"runtime": "python", "framework": "fastapi"}, {}).language == "python"
    assert detect_stack({"runtime": "node", "framework": "express"}, {}).language == "javascript"
    assert detect_stack({"runtime": "node", "framework": "react"}, {}).kind == "frontend"
    # fallback to mapping-tree languages when no metadata
    mt = {"symbols": {"a::x": {"language": "typescript"}, "a::y": {"language": "typescript"}}}
    p = detect_stack({}, mt)
    assert p.language == "typescript" and p.detected_from == "mapping_tree"
    assert detect_stack({}, {}).language == "unknown"


# --- handlers ---
def test_handler_selection_and_mcp_flag():
    assert select_handler(detect_stack({"runtime": "python"}, {})).key == "python"
    assert select_handler(detect_stack({"runtime": "python"}, {})).mcp_capable is True
    assert select_handler(detect_stack({"runtime": "node"}, {})).key == "node"
    assert select_handler(detect_stack({"runtime": "node"}, {})).mcp_capable is False
    assert select_handler(detect_stack({"language": "go"}, {})).key == "generic"


def test_prompt_is_stack_parameterized():
    react = detect_stack({"runtime": "node", "framework": "react"}, {})
    sys_msg = build_messages(react, REQS, MT_EMPTY, {})[0]["content"]
    assert "react" in sys_msg.lower()
    assert "React Testing Library" in sys_msg
    java = detect_stack({"language": "java", "framework": "spring"}, {})
    assert "JUnit" in build_messages(java, REQS, MT_EMPTY, {})[0]["content"]


# --- MCP capability ---
def test_mcp_supports_python_only():
    assert mcp_adapter.supports(detect_stack({"runtime": "python"}, {})) is True
    assert mcp_adapter.supports(detect_stack({"runtime": "node"}, {})) is False
    assert mcp_adapter.is_available() is False  # POC: no URL


def test_normalize_code_to_cases():
    inner = json.dumps({"tests": [{"path": "t/test_a.py", "content": "def test_a(): assert True"}]})
    genie = {"stepInformation": {}, "fileContents": {"1_tests": inner}}
    cases = mcp_adapter.normalize_response(genie)
    assert len(cases) == 1
    assert cases[0]["type"] == "generated"
    assert cases[0]["expected"]["test_file"].startswith("def test_a")
    assert mcp_adapter.normalize_response({"fileContents": {"x": "no json"}}) == []


# --- routing (simulate MCP up via monkeypatch, restore after) ---
def _with_mcp(monkey, available, healthy, gen):
    saved = (mcp_adapter.is_available, mcp_adapter.health, mcp_adapter.generate_test_cases)
    mcp_adapter.is_available = lambda cfg=None: available
    mcp_adapter.health = lambda cfg=None: healthy
    mcp_adapter.generate_test_cases = gen
    return saved


def _restore(saved):
    mcp_adapter.is_available, mcp_adapter.health, mcp_adapter.generate_test_cases = saved


def _fake_llm(_messages):
    return json.dumps({"test_cases": [{"id": "TC-1", "req_id": "REQ-1", "type": "happy_path"}]})


def test_routing_python_uses_mcp():
    saved = _with_mcp(None, True, True, lambda r, m, s: [{"id": "TC-GEN-1", "req_id": "", "type": "generated"}])
    try:
        _, src = router.derive_test_cases(REQS, MT_EMPTY, {}, tech_stack={"runtime": "python"}, llm=_fake_llm, use_cache=False)
        assert src == "mcp"
    finally:
        _restore(saved)


def test_routing_node_never_uses_mcp():
    saved = _with_mcp(None, True, True, lambda r, m, s: [{"id": "X"}])
    try:
        _, src = router.derive_test_cases(REQS, MT_EMPTY, {}, tech_stack={"runtime": "node"}, llm=_fake_llm, use_cache=False)
        assert src == "direct_llm"
    finally:
        _restore(saved)


def test_routing_mcp_error_falls_back():
    def boom(r, m, s):
        raise RuntimeError("mcp down")

    saved = _with_mcp(None, True, True, boom)
    try:
        cases, src = router.derive_test_cases(REQS, MT_EMPTY, {}, tech_stack={"runtime": "python"}, llm=_fake_llm, use_cache=False)
        assert src == "direct_llm" and len(cases) == 1
    finally:
        _restore(saved)


def test_cache_key_varies_by_stack():
    k_py = tcd_cache.cache_key(REQS, MT_EMPTY, {}, "python")
    k_js = tcd_cache.cache_key(REQS, MT_EMPTY, {}, "javascript")
    assert k_py != k_js


def _run_all():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")


if __name__ == "__main__":
    _run_all()
    print("\nAll Stage B stack-routing tests passed.")
