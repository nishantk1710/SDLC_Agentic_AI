"""LangGraph workflow definition.

The graph orchestrates the agents in sequence. Today it runs a single node
(code generation); add the remaining agents by registering more nodes and
edges below — the README's pipeline is:

    code_generator -> code_review -> refactoring -> debugging
                   -> unit_test -> documentation -> security
"""

from langgraph.graph import END, START, StateGraph

from app.graph import nodes
from app.graph.state import WorkflowState


def build_graph():
    """Build and compile the workflow graph."""
    graph = StateGraph(WorkflowState)

    graph.add_node("code_generator", nodes.code_generator_node)

    graph.add_edge(START, "code_generator")
    graph.add_edge("code_generator", END)

    return graph.compile()


# Compiled once at import; FastAPI invokes this.
workflow = build_graph()
