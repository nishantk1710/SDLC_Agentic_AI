"""Conditional routing for the IMP-001 subgraph.

The fixed gate IS the router source: these functions read state written by the deterministic
nodes and decide the next edge. The local repair cap is enforced here and is SEPARATE from the
orchestrator's ``attempt`` (which this service never touches).
"""

from __future__ import annotations

from langgraph.graph import END

from app.graph.state import WorkflowState

#: Local repair cap — how many repair attempts a single work item gets before escalation.
REPAIR_CAP = 3


def route_after_select(state: WorkflowState) -> str:
    """After selecting: generate the picked item, or run the final review when the plan is done.

    The plan-exhausted path leads to ``code_review`` (runs ONCE over the whole repo) before the
    graph ends. The escalation path (a failed item → human_review) bypasses this entirely, so the
    review only runs on a clean completion.
    """
    return "code_generator" if state.get("current_work_item") is not None else "code_review"


def route_after_codegen(state: WorkflowState) -> str:
    """After generation: run the gate on success, or escalate a failed item (no gate/commit).

    A generation failure (invalid model output after retry → no files) must NOT reach the gate
    or produce a commit; it is flagged for human review.
    """
    return "gate" if state.get("codegen_ok", True) else "escalate"


def route_after_gate(state: WorkflowState) -> str:
    """The gate decision: all-pass → commit; fail under cap → repair; fail at cap → escalate."""
    gate_result = state.get("gate_result")
    if gate_result and gate_result.get("passed"):
        return "commit"
    if int(state.get("repair_attempt", 0)) < REPAIR_CAP:
        return "repair"
    return "escalate"
