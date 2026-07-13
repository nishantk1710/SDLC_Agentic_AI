# exec-sandbox — MCP execution server

A standalone MCP server (FastMCP, `mcp` SDK) that runs commands, edits files, and drives git
inside a locked-down Linux sandbox. It lives **outside** `services/implementation/app/`; the
only in-app client is `app/integrations/executor.py` (`MCPExecutor`).

## Tools (mirror the executor primitives)

| Tool | Purpose |
|---|---|
| `run_command(cmd, cwd, timeout)` | Run an argv command in the jailed workspace → `{stdout, stderr, exit_code, timed_out}` |
| `write_file(path, content)` / `read_file(path)` | Jailed file I/O |
| `git_status(project_dir)` / `git_diff(project_dir)` | Read-only git inspection |
| `git_commit(project_dir, message)` | Fixed-path commit (audit checkpoint) |
| `install_package(name, manager)` | Workspace-scoped install; `manager` ∈ {`pip`, `npm`} |

## Baked-in rules

- **Path jail:** every path resolves under `WORKSPACE_ROOT`; escapes raise `WorkspaceEscapeError`.
- **Bounded execution:** each `run_command` has a hard timeout (`COMMAND_TIMEOUT`) and output cap
  (`MAX_OUTPUT_BYTES`).
- **Workspace-scoped installs:** pip uses `--target .py_packages`; npm installs local
  `node_modules`. Never global/system.
- **Transport:** streamable-HTTP (not stdio), mounted at `/mcp`.

## Egress lockdown (PyPI + npm only)

The sandbox joins only `sandbox_internal` (`internal: true`) — no internet. Its sole outbound
path is the `egress-proxy` (squid), which allows connections **only** to the registry domains in
[`egress/squid.conf`](egress/squid.conf) and denies everything else. `HTTP(S)_PROXY` on the
sandbox route pip/npm through it. See `docker-compose.yml` at the repo root.

## Build & run

```bash
# from the repo root
docker compose build exec-sandbox
docker compose up -d exec-sandbox egress-proxy

# acceptance (no agent): runs `echo hi` and lists the registered tools inside the container
docker compose exec exec-sandbox python smoke_test.py
docker compose exec exec-sandbox curl -s localhost:8080/mcp   # endpoint is up
```

## Local check (no Docker)

`python smoke_test.py` runs the same logic checks on the host (run_command, path jail, tool
registration). On Windows it falls back from `echo` to a portable command; the literal
`echo hi` path is exercised in the Linux container.

## Windows / PowerShell change point

Swap the `Dockerfile` base image for a Windows base + install `pwsh`; `run_command` then targets
PowerShell instead of bash. Jailing, timeouts, installs, and transport are unchanged.
