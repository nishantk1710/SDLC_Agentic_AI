"""Standalone acceptance smoke test for exec-sandbox (no agent, no Docker required).

Runs from this directory:  python smoke_test.py

Checks:
  1. run_command executes `echo hi` and returns exit_code 0 (falls back to a portable command
     on hosts without an `echo` executable, e.g. Windows — the real target is Linux+bash).
  2. The MCP server registers exactly the seven executor-primitive tools (in-process equivalent
     of "curl the endpoint lists the tools"). Skipped only if the mcp SDK is not installed.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Ensure sandbox/server are importable regardless of CWD, and jail to a temp workspace.
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("WORKSPACE_ROOT", tempfile.mkdtemp(prefix="exec-sandbox-smoke-"))

import sandbox  # noqa: E402


def check_run_command() -> None:
    result = sandbox.run_command(["echo", "hi"])
    note = "echo"
    if result["exit_code"] == 127:  # no `echo` exe on this host — portable fallback
        result = sandbox.run_command([sys.executable, "-c", "print('hi')"])
        note = "python-fallback"
    assert result["exit_code"] == 0, result
    assert "hi" in result["stdout"], result
    print(f"[ok] run_command echo hi -> exit_code {result['exit_code']} ({note})")


def check_path_jail() -> None:
    try:
        sandbox.read_file("../../etc/passwd")
    except sandbox.WorkspaceEscapeError:
        print("[ok] path jail rejects workspace escape")
        return
    raise AssertionError("path jail did NOT reject an escaping path")


def check_tools_registered() -> None:
    try:
        import server
    except ModuleNotFoundError as exc:
        print(f"[skip] tool-list check (mcp not installed: {exc})")
        return
    tools = asyncio.run(server.mcp.list_tools())
    names = sorted(t.name for t in tools)
    expected = sorted(sandbox.TOOL_NAMES)
    assert names == expected, f"registered {names} != expected {expected}"
    print(f"[ok] MCP tools registered: {names}")


if __name__ == "__main__":
    check_run_command()
    check_path_jail()
    check_tools_registered()
    print("SMOKE OK")
