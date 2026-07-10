"""LangGraph node functions.

Each node wraps one step of the IMP-001 subgraph. Agents are instantiated once at import and
reused. The executor is resolved at run time via the provider (``get_executor``), so the same
node code works with the real MCP sandbox (set in the app lifespan) or a FakeExecutor (set in
tests).
"""

from __future__ import annotations

from langgraph.types import interrupt

from app.agents.code_generator import CodeGeneratorAgent
from app.graph.state import GateCheck, WorkflowState
from app.integrations.executor import get_executor

_code_generator = CodeGeneratorAgent()


def code_generator_node(state: WorkflowState) -> WorkflowState:
    """LLM: generate + write files for the current work item (no gate/commit here)."""
    return _code_generator.execute(state)


def select_work_item_node(state: WorkflowState) -> WorkflowState:
    """Advance the cursor to the next work item; reset the LOCAL repair counter.

    When the plan is exhausted, clears current_work_item and marks the run completed.
    """
    items = state.get("work_items") or []
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
    """FIXED, deterministic quality gate: compile → build → test → lint, in order.

    Short-circuits on the first failing check and records ``gate_result`` (which check failed +
    captured stderr). This node is the ROUTER source; it makes no routing decision itself.
    """
    executor = get_executor()
    project_dir = state.get("project_id") or state.get("run_id") or "project"
    checks: list[GateCheck] = []
    for run_check in (executor.compile, executor.build, executor.test, executor.lint):
        result = run_check(project_dir)
        checks.append(
            {"name": result.name, "passed": result.passed, "stderr": result.stderr, "exit_code": result.exit_code}
        )
        if not result.passed:
            break  # short-circuit — don't run later checks once one fails
    state["gate_result"] = {"passed": all(c["passed"] for c in checks), "checks": checks}
    return state


def commit_node(state: WorkflowState) -> WorkflowState:
    """FIXED: commit the current work item's files. Reached ONLY on an all-pass gate."""
    executor = get_executor()
    project_dir = state.get("project_id") or state.get("run_id") or "project"
    work_item = state.get("current_work_item")
    item_id = work_item.id if work_item is not None else "work-item"
    message = f"IMP-001 {item_id}: {', '.join(state.get('generated_code', [])) or 'no files'}"
    executor.git_commit(project_dir, message)  # LLM never forms/executes this call (rule 2)
    return state


def escalate_node(state: WorkflowState) -> WorkflowState:
    """Local repair cap reached: flag for human review (status persisted before the interrupt)."""
    state["workflow_status"] = "needs_human_review"
    return state


def human_review_node(state: WorkflowState) -> WorkflowState:
    """HITL pause. interrupt() suspends the run for a human decision (needs a checkpointer)."""
    interrupt({"reason": "needs_human_review", "run_id": state.get("run_id")})
    return state  # reached only after a human resumes the run
