"""LangGraph node functions.

Each node wraps one step of the IMP-001 subgraph. Agents are instantiated once at import and
reused. The executor is resolved at run time via the provider (``get_executor``), so the same
node code works with the real MCP sandbox (set in the app lifespan) or a FakeExecutor (set in
tests).
"""

from __future__ import annotations

import logging

from langgraph.types import interrupt

from app.agents.code_generator import CodeGeneratorAgent
from app.agents.code_review import CodeReviewAgent
from app.graph.state import GateCheck, WorkflowState
from app.integrations.executor import get_executor

logger = logging.getLogger(__name__)

_code_generator = CodeGeneratorAgent()
_code_review = CodeReviewAgent()


def code_generator_node(state: WorkflowState) -> WorkflowState:
    """LLM: generate + write files for the current work item (no gate/commit here)."""
    return _code_generator.execute(state)


def code_review_node(state: WorkflowState) -> WorkflowState:
    """Clone the repo into an ephemeral sandbox, run static analysis, write the review report.

    The agent owns the whole sandbox session (clone → ruff/eslint → sonar-scanner → teardown);
    this node just delegates. Runs ONCE after the plan is exhausted.
    """
    return _code_review.execute(state)


def select_work_item_node(state: WorkflowState) -> WorkflowState:
    """Advance the cursor to the next work item; reset the LOCAL repair counter.

    When the plan is exhausted, clears current_work_item and marks the run completed.
    """
    items = state.get("work_items", [])
    if not isinstance(items, list):  # fail fast on malformed input, don't crash mid-loop
        raise ValueError(f"work_items must be a list, got {type(items).__name__}")
    index = int(state.get("work_item_index", 0))
    if index < len(items):
        state["current_work_item"] = items[index]
        state["work_item_index"] = index + 1
        state["repair_attempt"] = 0  # LOCAL, reset per work item (never touches `attempt`)
    else:
        state["current_work_item"] = None
        state["workflow_status"] = "completed"
    return state


def gate_node(state: WorkflowState) -> WorkflowState:
    """FIXED, deterministic quality gate for the code-generation phase: compile → build.

    Short-circuits on the first failing check and records ``gate_result`` (which check failed +
    captured stderr). An executor/sandbox error (timeout, network partition) is treated as a
    gate failure — recorded as a failing check — rather than crashing the graph. This node is
    the ROUTER source; it makes no routing decision itself.

    NOTE: ``test`` and ``lint`` are intentionally NOT run here. This agent only generates source
    code — there are no unit tests yet (``pytest`` on test-less code exits 5 "no tests
    collected"), and lint/coverage belong to the later pipeline agents that own them (Unit Test,
    Review, Security). The executor still exposes ``test``/``lint`` for those stages.
    """
    executor = get_executor()
    project_dir = state.get("project_id") or state.get("run_id") or "project"
    checks: list[GateCheck] = []
    for run_check in (executor.compile, executor.build):
        try:
            result = run_check(project_dir)
        except Exception as exc:  # noqa: BLE001 - executor failure becomes a gate failure, not a crash
            logger.exception("gate: %s raised for run %s", run_check.__name__, state.get("run_id"))
            checks.append(
                {"name": run_check.__name__, "passed": False, "stderr": f"executor error: {exc}", "exit_code": -1}
            )
            break
        checks.append(
            {"name": result.name, "passed": result.passed, "stderr": result.stderr, "exit_code": result.exit_code}
        )
        if not result.passed:
            break  # short-circuit — don't run later checks once one fails
    state["gate_result"] = {"passed": bool(checks) and all(c["passed"] for c in checks), "checks": checks}
    return state


def commit_node(state: WorkflowState) -> WorkflowState:
    """FIXED: commit the current work item's files. Reached ONLY on an all-pass gate."""
    executor = get_executor()
    project_dir = state.get("project_id") or state.get("run_id") or "project"
    work_item = state.get("current_work_item")
    item_id = work_item.id if work_item is not None else "work-item"
    message = f"IMP-001 {item_id}: {', '.join(state.get('generated_code', [])) or 'no files'}"
    try:
        executor.git_commit(project_dir, message)  # LLM never forms/executes this call (rule 2)
    except Exception as exc:  # noqa: BLE001 - don't crash the run on a commit failure
        logger.exception("commit failed for run %s", state.get("run_id"))
        state["generation_summary"] = (state.get("generation_summary") or "") + f"[commit] FAILED for {item_id}: {exc}\n"
    return state


def escalate_node(state: WorkflowState) -> WorkflowState:
    """Local repair cap reached: flag for human review (status persisted before the interrupt)."""
    state["workflow_status"] = "needs_human_review"
    return state


def human_review_node(state: WorkflowState) -> WorkflowState:
    """HITL pause. interrupt() suspends the run for a human decision (needs a checkpointer)."""
    interrupt({"reason": "needs_human_review", "run_id": state.get("run_id")})
    return state  # reached only after a human resumes the run
