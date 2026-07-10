# exec-sandbox — Linux sandbox running the MCP server (bash + python3.12 + node + tsc).
#
# WINDOWS/POWERSHELL CHANGE POINT:
#   Swap this base image for a Windows base image (e.g. mcr.microsoft.com/windows/servercore
#   or a python-on-windows image) and install PowerShell (pwsh). The sandbox's run_command
#   then targets pwsh instead of bash. Everything else (jailing, timeouts, workspace-scoped
#   installs, streamable-HTTP) is unchanged.
FROM python:3.12-slim

# bash (default shell for run_command), git (git_* tools), node + npm + tsc (frontend build),
# curl/gnupg to add the NodeSource apt repo.
RUN apt-get update \
 && apt-get install -y --no-install-recommends bash git curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g typescript \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/exec-sandbox

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sandbox.py server.py ./

# Sandbox configuration (all overridable via compose / env).
ENV WORKSPACE_ROOT=/workspace \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    COMMAND_TIMEOUT=120 \
    INSTALL_TIMEOUT=300 \
    MAX_OUTPUT_BYTES=1000000

RUN mkdir -p /workspace
EXPOSE 8080

# streamable-HTTP MCP server, mounted at /mcp.
CMD ["python", "server.py"]
