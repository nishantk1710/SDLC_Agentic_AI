"""Refactoring Agent (LLM + tools) — applies a code-review report's findings to the code.

Pipeline position (DEVELOPER_GUIDE.md §1): runs after Code Review. It READS ``review_report``
(the code-review stage's output, a report like the reviewer's ``code-review.md``) and WRITES
``refactored_code`` — its own field only. It never touches ``generated_code`` or another agent's
output (guide rule 3).

What it does, in order:
  1. Parse the report -> the target repository URL (if any) + the actionable findings.
  2. Make sure the code is in the sandbox: use the files code_generator already wrote this run
     (``generated_code``); or, for a standalone report that names an external repo, clone it via
     the executor (FIXED path — the node forms the ``git clone`` argv; the model never does).
  3. For each file with findings: read it, ask the model (through ``self.llm``) for the full
     corrected file as STRICT JSON, and write the fix back through the executor.
  4. Record a human-readable summary in ``refactored_code``.

Rules honored (CLAUDE.md + guide):
- ``self.llm`` is the ONLY model access — no provider SDK import.
- All reads/writes/exec go through the injected :class:`Executor` — never open files or shell out.
- Fixes are proposed by the model but written by the fixed code (like the repair path); the model
  gets only the read-only repair tools (no ``git_commit``). This agent does NOT gate or commit.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.agents.base import BaseAgent
from app.agents.code_generator import _extract_json
from app.graph.state import WorkflowState
from app.integrations import github
from app.integrations.executor import Executor, get_executor
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

#: Safety bound so one report can't fan out into an unbounded number of LLM calls. If a report
#: exceeds this, the extra files are left for a follow-up pass and the omission is surfaced in the
#: summary (never silently dropped).
MAX_FILES_PER_RUN = 25


@dataclass(frozen=True)
class Finding:
    """One actionable review finding parsed from the report."""

    severity: str
    file: str
    location: str
    description: str


class RefactoringAgent(BaseAgent):
    name = "refactoring"

    def __init__(self, executor: Executor | None = None, llm: LLMGateway | None = None) -> None:
        super().__init__()
        if llm is not None:  # allow test/DI override of the gateway singleton
            self.llm = llm
        self._executor = executor

    def _resolve_executor(self) -> Executor:
        return self._executor if self._executor is not None else get_executor()

    def execute(self, state: WorkflowState) -> WorkflowState:
        report = state.get("review_report") or ""
        if not report.strip():
            # Nothing upstream produced a report — clean no-op (a code_review stage fills this).
            state["refactored_code"] = "[refactoring] no review_report on state — nothing to do"
            return state

        executor = self._resolve_executor()
        project_dir = state.get("project_id") or state.get("run_id") or "project"
        lines: list[str] = []

        repo_url = github.normalize_repo_url(_parse_repository(report))
        findings = _parse_findings(report)
        by_file = _group_by_file(findings)
        lines.append(
            f"[refactoring] repo={repo_url or 'in-place'} project={project_dir} "
            f"| parsed {len(findings)} finding(s) across {len(by_file)} file(s)"
        )

        # Ensure the code is present. In-pipeline: code_generator already wrote it. Standalone: the
        # report names a repo -> clone it (fixed path). Cloning needs sandbox egress to the host.
        if not state.get("generated_code") and repo_url is not None:
            lines.append(self._clone(executor, repo_url, project_dir))

        if not by_file:
            lines.append("[refactoring] no actionable findings in the report's Findings section")
            state["refactored_code"] = "\n".join(lines) + "\n"
            state["workflow_status"] = "refactored"
            return state

        files = sorted(by_file)  # deterministic order
        if len(files) > MAX_FILES_PER_RUN:
            lines.append(
                f"[refactoring] NOTE: {len(files)} files with findings; applying the first "
                f"{MAX_FILES_PER_RUN}, deferring {len(files) - MAX_FILES_PER_RUN} to a follow-up pass"
            )
            files = files[:MAX_FILES_PER_RUN]

        system = self._load_prompt("refactoring")
        changed: list[str] = []
        for rel in files:
            lines.append(self._apply_file(executor, project_dir, rel, by_file[rel], system, changed))

        lines.append(
            f"[refactoring] changed {len(changed)} file(s): {', '.join(changed) or '(none)'}"
        )
        state["refactored_code"] = "\n".join(lines) + "\n"
        state["workflow_status"] = "refactored"
        return state

    # -- steps ----------------------------------------------------------------

    def _clone(self, executor: Executor, repo_url: str, project_dir: str) -> str:
        """Clone the report's repo into the sandbox (fixed path). Best-effort; records the outcome."""
        try:
            result = executor.run_command(github.clone_command(repo_url, project_dir))
        except Exception as exc:  # noqa: BLE001 - a clone failure must not crash the run
            logger.warning("refactoring: clone raised for %s: %s", repo_url, exc)
            return f"[refactoring] clone FAILED ({repo_url}): {exc}"
        if not result.ok:
            return (
                f"[refactoring] clone FAILED ({repo_url}) exit={result.exit_code}: "
                f"{(result.stderr or '').strip()[:200]} "
                "(sandbox egress may not allow this host — see integrations/github.py)"
            )
        return f"[refactoring] cloned {repo_url} -> {project_dir}"

    def _apply_file(
        self,
        executor: Executor,
        project_dir: str,
        rel: str,
        file_findings: list[Finding],
        system: str,
        changed: list[str],
    ) -> str:
        """Read one file, ask the model for the corrected content, write the fix back."""
        sandbox_path = f"{project_dir}/{rel.lstrip('/')}"
        try:
            current = executor.read_file(sandbox_path)
        except Exception:  # noqa: BLE001 - a missing file just means we can't fix it here
            return f"[refactoring] {rel}: SKIPPED — not found in sandbox ({len(file_findings)} finding(s))"

        prompt = _build_prompt(rel, current, file_findings)
        # Read-only repair tools let the model inspect neighbours; it never commits (rule 2).
        raw = self.llm.complete_with_tools(prompt=prompt, system=system, tools=executor.get_repair_tools())

        fixes = _parse_files(raw)
        if not fixes:
            logger.warning("refactoring: no valid fix parsed for %s", sandbox_path)
            return f"[refactoring] {rel}: SKIPPED — model returned no valid fix ({len(file_findings)} finding(s))"

        wrote: list[str] = []
        for entry in fixes:
            target = _under_project(project_dir, entry["path"])
            executor.write_file(target, entry["content"])
            wrote.append(target)
            if target not in changed:
                changed.append(target)
        return f"[refactoring] {rel}: applied {len(file_findings)} finding(s) -> wrote {', '.join(wrote)}"


# --------------------------------------------------------------------------- report parsing


def _parse_repository(report: str) -> str | None:
    """Pull the ``Repository: <url>`` line out of the report header (first match wins)."""
    match = re.search(r"(?im)^\s*Repository\s*:\s*(\S+)\s*$", report)
    return match.group(1) if match else None


def _findings_section(report: str) -> str:
    """Return only the human-authored ``Findings`` block.

    The report's later ``Static analysis details`` / ``Notes`` sections carry hundreds of
    generated-bundle lint lines the report itself calls noise — parsing those would try to "fix"
    third-party bundled code. We scope to the actionable Findings section only.
    """
    start = re.search(r"(?im)^\s*Findings\s*$", report)
    if not start:
        return report  # no explicit section header — scan the whole report
    body = report[start.end():]
    end = re.search(r"(?im)^\s*(Notes|Static analysis details|Static Analysis)\s*$", body)
    return body[: end.start()] if end else body


def _parse_findings(report: str) -> list[Finding]:
    """Parse ``[severity] <file> (<loc>) — <description>`` lines from the Findings section."""
    findings: list[Finding] = []
    for line in _findings_section(report).splitlines():
        parsed = _parse_finding_line(line.strip())
        if parsed is not None:
            findings.append(parsed)
    return findings


def _parse_finding_line(line: str) -> Finding | None:
    """Parse one finding line. Procedural (not one mega-regex) so odd spacing/paths still parse."""
    head = re.match(r"^\[(?P<sev>[A-Za-z]+)\]\s+(?P<rest>.+)$", line)
    if not head:
        return None
    rest = head.group("rest")

    file_match = re.match(r"^(?P<file>[^\s(]+)", rest)
    if not file_match:
        return None
    file = file_match.group("file")
    rest = rest[file_match.end():].lstrip()

    location = ""
    if rest.startswith("("):
        loc_match = re.match(r"^\(([^)]*)\)", rest)
        if loc_match:
            location = loc_match.group(1).strip()
            rest = rest[loc_match.end():].lstrip()

    description = rest.lstrip("—-:").strip()  # em dash / hyphen / colon separators
    return Finding(severity=head.group("sev").lower(), file=file, location=location, description=description)


def _group_by_file(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.file, []).append(finding)
    return grouped


# --------------------------------------------------------------------------- prompt + fix parsing


def _build_prompt(rel: str, current: str, file_findings: list[Finding]) -> str:
    findings_block = "\n".join(
        f"- [{f.severity}] {f.location or '(no location)'}: {f.description}" for f in file_findings
    )
    return (
        f"File to fix: {rel}\n\n"
        f"Review findings for this file:\n{findings_block}\n\n"
        f"Current content of {rel}:\n"
        f"```\n{current}\n```\n\n"
        'Return the corrected file as STRICT JSON: {"files":[{"path":...,"content":...}],"notes":...}'
    )


def _parse_files(raw: str) -> list[dict[str, str]] | None:
    """Parse the model reply into a list of {path, content}. Mirrors repair/code_generator."""
    obj = _extract_json(raw)
    if not isinstance(obj, dict) or not isinstance(obj.get("files"), list):
        return None
    clean: list[dict[str, str]] = []
    for entry in obj["files"]:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str) and isinstance(entry.get("content"), str):
            clean.append({"path": entry["path"], "content": entry["content"]})
    return clean or None


def _under_project(project_dir: str, path: str) -> str:
    """Normalize a model-returned path to live under the project dir (idempotent)."""
    rel = path.lstrip("/")
    prefix = f"{project_dir}/"
    return rel if rel == project_dir or rel.startswith(prefix) else f"{prefix}{rel}"


# Module-level agent reused across invocations (guide's node pattern). Executor + gateway are
# resolved at run time, so tests inject via set_executor / monkeypatch (like repair_node).
_refactoring_agent = RefactoringAgent()


def refactoring_node(state: WorkflowState) -> WorkflowState:
    return _refactoring_agent.execute(state)
