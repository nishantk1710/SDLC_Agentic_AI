"""Sandbox primitives for the exec-sandbox MCP server.

Pure logic with NO mcp dependency, so it is unit-testable on its own (see smoke_test.py).
``server.py`` wraps these as FastMCP tools.

Hard rules baked in (CLAUDE.md rules 5/6):
- Every path is jailed under ``WORKSPACE_ROOT``; anything escaping it is rejected.
- ``run_command`` has a hard timeout and an output-size cap.
- ``install_package`` is workspace-scoped only (pip ``--target`` / local ``node_modules``),
  never global/system.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace")).resolve()
DEFAULT_TIMEOUT = float(os.environ.get("COMMAND_TIMEOUT", "120"))
MAX_OUTPUT_BYTES = int(os.environ.get("MAX_OUTPUT_BYTES", str(1_000_000)))

# Git identity used for fixed-path commits (avoids requiring container git config).
_GIT_IDENTITY = ["-c", "user.email=sandbox@local", "-c", "user.name=exec-sandbox"]

# The tools server.py registers — kept here so tests can assert the set without importing mcp.
TOOL_NAMES = [
    "run_command",
    "write_file",
    "read_file",
    "git_status",
    "git_diff",
    "git_commit",
    "install_package",
]


class WorkspaceEscapeError(ValueError):
    """Raised when a requested path resolves outside WORKSPACE_ROOT."""


def _resolve(rel: str) -> Path:
    """Resolve ``rel`` under WORKSPACE_ROOT, rejecting any path that escapes the jail."""
    candidate = (WORKSPACE_ROOT / rel).resolve()
    if candidate != WORKSPACE_ROOT and WORKSPACE_ROOT not in candidate.parents:
        raise WorkspaceEscapeError(f"path escapes WORKSPACE_ROOT: {rel!r}")
    return candidate


def _cap(text: str) -> str:
    """Cap captured output to MAX_OUTPUT_BYTES characters."""
    if len(text) <= MAX_OUTPUT_BYTES:
        return text
    return text[:MAX_OUTPUT_BYTES] + "\n...[output truncated]"


def run_command(cmd: list[str], cwd: str = ".", timeout: float | None = None) -> dict:
    """Run ``cmd`` (argv list) in the jailed ``cwd``. Never raises for exec failures.

    Returns ``{stdout, stderr, exit_code, timed_out}``.
    """
    workdir = _resolve(cwd)
    workdir.mkdir(parents=True, exist_ok=True)
    limit = float(timeout) if timeout else DEFAULT_TIMEOUT
    try:
        proc = subprocess.run(
            list(cmd), cwd=str(workdir), capture_output=True, text=True, timeout=limit
        )
        return {
            "stdout": _cap(proc.stdout),
            "stderr": _cap(proc.stderr),
            "exit_code": proc.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": _cap(exc.stdout or "" if isinstance(exc.stdout, str) else ""),
            "stderr": _cap((exc.stderr if isinstance(exc.stderr, str) else "") + f"\n[timed out after {limit}s]"),
            "exit_code": 124,
            "timed_out": True,
        }
    except FileNotFoundError as exc:
        return {"stdout": "", "stderr": f"command not found: {cmd[0]!r} ({exc})", "exit_code": 127, "timed_out": False}


def write_file(path: str, content: str) -> dict:
    """Write ``content`` to the jailed ``path`` (creating parents)."""
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "bytes": len(content.encode("utf-8"))}


def read_file(path: str) -> str:
    """Return the text content of the jailed ``path``."""
    return _resolve(path).read_text(encoding="utf-8")


def git_status(project_dir: str = ".") -> str:
    """Read-only ``git status --porcelain`` for the jailed project dir."""
    result = run_command(["git", "status", "--porcelain"], cwd=project_dir)
    return result["stdout"] + result["stderr"]


def git_diff(project_dir: str = ".") -> str:
    """Read-only ``git diff`` for the jailed project dir."""
    result = run_command(["git", "diff"], cwd=project_dir)
    return result["stdout"] + result["stderr"]


def git_commit(project_dir: str, message: str) -> dict:
    """Fixed-path commit: stage all, commit with a fixed identity, return the resulting sha."""
    add = run_command(["git", *_GIT_IDENTITY, "add", "-A"], cwd=project_dir)
    if add["exit_code"] != 0:
        return {"committed": False, "sha": None, "stdout": add["stdout"], "stderr": add["stderr"], "exit_code": add["exit_code"]}
    commit = run_command(["git", *_GIT_IDENTITY, "commit", "-m", message], cwd=project_dir)
    sha = None
    if commit["exit_code"] == 0:
        sha = run_command(["git", "rev-parse", "HEAD"], cwd=project_dir)["stdout"].strip() or None
    return {
        "committed": commit["exit_code"] == 0,
        "sha": sha,
        "stdout": commit["stdout"],
        "stderr": commit["stderr"],
        "exit_code": commit["exit_code"],
    }


def install_package(name: str, manager: str = "pip", cwd: str = ".") -> dict:
    """Install a dependency workspace-scoped only. ``manager`` in {pip, npm}.

    pip → ``pip install --target <cwd>/.py_packages`` (never system/global).
    npm → ``npm install`` into the local ``node_modules`` of ``cwd``.
    """
    if manager == "pip":
        cmd = ["python", "-m", "pip", "install", "--no-input", "--target", ".py_packages", name]
    elif manager == "npm":
        cmd = ["npm", "install", "--no-save", name]
    else:
        return {"stdout": "", "stderr": f"unsupported manager: {manager!r} (use 'pip' or 'npm')", "exit_code": 2, "timed_out": False}
    return run_command(cmd, cwd=cwd, timeout=float(os.environ.get("INSTALL_TIMEOUT", "300")))
