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
    """After selecting: generate code for the picked item, or finish when the plan is exhausted."""
    return "code_generator" if state.get("current_work_item") is not None else END


def route_after_gate(state: WorkflowState) -> str:
    """The gate decision: all-pass → commit; fail under cap → repair; fail at cap → escalate."""
    gate_result = state.get("gate_result")
    if gate_result and gate_result.get("passed"):
        return "commit"
    if int(state.get("repair_attempt", 0)) < REPAIR_CAP:
        return "repair"
    return "escalate"
