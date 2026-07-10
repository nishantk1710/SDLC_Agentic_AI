"""exec-sandbox — standalone MCP server (FastMCP, mcp SDK), served over streamable-HTTP.

Exposes the executor primitives as MCP tools, all backed by :mod:`sandbox` (jailed to
WORKSPACE_ROOT, timeout+output caps, workspace-scoped installs). This process runs INSIDE the
sandbox container; ``app/integrations/executor.py`` (MCPExecutor) is its only in-app client.

Run:  python server.py            # transport=streamable-http, mounts at /mcp
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

import sandbox

mcp = FastMCP(
    "exec-sandbox",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8080")),
)


@mcp.tool()
def run_command(cmd: list[str], cwd: str = ".", timeout: float | None = None) -> dict:
    """Run a command (argv list) in the jailed workspace. Returns stdout/stderr/exit_code/timed_out."""
    return sandbox.run_command(cmd, cwd, timeout)


@mcp.tool()
def write_file(path: str, content: str) -> dict:
    """Write content to a workspace-relative path (jailed)."""
    return sandbox.write_file(path, content)


@mcp.tool()
def read_file(path: str) -> str:
    """Read a workspace-relative file (jailed)."""
    return sandbox.read_file(path)


@mcp.tool()
def git_status(project_dir: str = ".") -> str:
    """Read-only git status for a project dir."""
    return sandbox.git_status(project_dir)


@mcp.tool()
def git_diff(project_dir: str = ".") -> str:
    """Read-only git diff for a project dir."""
    return sandbox.git_diff(project_dir)


@mcp.tool()
def git_commit(project_dir: str, message: str) -> dict:
    """Stage all and commit (fixed-path audit checkpoint). Returns committed/sha/stderr."""
    return sandbox.git_commit(project_dir, message)


@mcp.tool()
def install_package(name: str, manager: str = "pip", cwd: str = ".") -> dict:
    """Install a dependency workspace-scoped only. manager in {pip, npm}."""
    return sandbox.install_package(name, manager, cwd)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
