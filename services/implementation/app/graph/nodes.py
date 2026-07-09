"""LangGraph node functions.

Each node wraps one agent's `execute` method. Agents are instantiated once at
import time and reused across workflow invocations.
"""

from app.agents.code_generator import CodeGeneratorAgent
from app.graph.state import WorkflowState

_code_generator = CodeGeneratorAgent()


def code_generator_node(state: WorkflowState) -> WorkflowState:
    return _code_generator.execute(state)
