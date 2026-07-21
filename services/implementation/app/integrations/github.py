"""GitHub integration — repo-URL handling for the refactoring flow.

Per DEVELOPER_GUIDE.md rule 6 ("outside tools live in ``integrations/`` — agents call those
wrappers, not the tools directly"), URL parsing/validation and the clone command shape live
here, NOT inside an agent.

This module does NOT shell out. Cloning must execute INSIDE the sandbox, so it only *builds*
the argv; the caller runs it through the single execution chokepoint
(``app/integrations/executor.py``). That keeps CLAUDE.md rule 5 intact ("nothing else shells
out; the sandbox is the boundary").

Note on egress: the exec-sandbox allowlist is PyPI + npm only (CLAUDE.md rule 6). A live
``git clone`` of a public host therefore only succeeds if that host is added to the sandbox
egress allowlist (``tools/exec-sandbox/squid.conf``); otherwise the code must already be present
in the workspace (the normal in-pipeline case, where code_generator wrote it earlier this run).
"""

from __future__ import annotations

import re

__all__ = ["normalize_repo_url", "repo_name", "clone_command"]

# http(s)://host/owner/repo(.git), git://host/..., or scp-style git@host:owner/repo(.git)
_HTTP_RE = re.compile(r"^(?:https?|git)://[\w.-]+(?::\d+)?/[\w./~-]+?(?:\.git)?/?$")
_SCP_RE = re.compile(r"^[\w.-]+@[\w.-]+:[\w./~-]+?(?:\.git)?/?$")


def normalize_repo_url(raw: str | None) -> str | None:
    """Return a cleaned git URL if ``raw`` looks like one, else ``None``.

    Accepts https/http/git URLs and scp-style ``git@host:owner/repo``. Rejects anything else so
    a malformed ``Repository:`` line in a report never becomes a clone argument.
    """
    if not raw:
        return None
    url = raw.strip().strip("<>").rstrip("/")
    if _HTTP_RE.match(url) or _SCP_RE.match(url):
        return url
    return None


def repo_name(url: str) -> str:
    """Derive a filesystem-safe project dir name from a repo URL (``.../foo.git`` -> ``foo``)."""
    tail = re.split(r"[/:]", url.rstrip("/"))[-1]
    tail = re.sub(r"\.git$", "", tail)
    slug = re.sub(r"[^\w.-]", "-", tail).strip("-")
    return slug or "repo"


def clone_command(url: str, dest: str, *, depth: int = 1) -> list[str]:
    """Build the ``git clone`` argv the executor runs inside the sandbox.

    Shallow by default (``--depth 1``) — the refactor works on a working tree, not history.
    """
    argv = ["git", "clone"]
    if depth and depth > 0:
        argv += ["--depth", str(depth)]
    argv += [url, dest]
    return argv
