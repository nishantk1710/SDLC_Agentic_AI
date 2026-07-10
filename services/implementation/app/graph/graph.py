"""LangGraph workflow definition — the IMP-001 code-generation subgraph.

Loops over the plan's work items; for each: generate → fixed gate → (commit | repair→gate |
escalate→HITL). The fixed gate is the router; the local repair cap lives in router.py.

    select ─▶ code_generator ─▶ gate ─┬─ all pass ───────────▶ commit ─▶ select (next / done)
       ▲                              ├─ fail & repair<CAP ──▶ repair ─▶ gate
       └────────── commit             └─ fail & repair>=CAP ─▶ escalate ─▶ human_review (interrupt)

Compiled with a checkpointer so the human-review interrupt() can pause the run for HITL.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.repair import repair_node
from app.graph import nodes
from app.graph.router import route_after_codegen, route_after_gate, route_after_select
from app.graph.state import WorkflowState


def build_graph():
    """Build and compile the IMP-001 workflow graph."""
    graph = StateGraph(WorkflowState)

    graph.add_node("select", nodes.select_work_item_node)
    graph.add_node("code_generator", nodes.code_generator_node)
    graph.add_node("gate", nodes.gate_node)
    graph.add_node("commit", nodes.commit_node)
    graph.add_node("repair", repair_node)
    graph.add_node("escalate", nodes.escalate_node)
    graph.add_node("human_review", nodes.human_review_node)

    graph.add_edge(START, "select")
    graph.add_conditional_edges("select", route_after_select, {"code_generator": "code_generator", END: END})
    graph.add_conditional_edges(
        "code_generator", route_after_codegen, {"gate": "gate", "escalate": "escalate"}
    )
    graph.add_conditional_edges(
        "gate", route_after_gate, {"commit": "commit", "repair": "repair", "escalate": "escalate"}
    )
    graph.add_edge("commit", "select")      # all-pass → next work item (or done)
    graph.add_edge("repair", "gate")        # repair → back to the fixed gate
    graph.add_edge("escalate", "human_review")
    graph.add_edge("human_review", END)

    # Checkpointer enables the human_review interrupt() to pause/resume (HITL).
    return graph.compile(checkpointer=MemorySaver())


# Compiled once at import; FastAPI invokes this.
workflow = build_graph()
