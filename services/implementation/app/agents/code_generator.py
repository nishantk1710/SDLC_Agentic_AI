"""Code Generation Agent — first step of the implementation workflow.

Reads the design package from the shared state and produces source code.
"""

from app.agents.base import BaseAgent
from app.graph.state import WorkflowState


class CodeGeneratorAgent(BaseAgent):
    name = "code_generator"

    def execute(self, state: WorkflowState) -> WorkflowState:
        system = self._load_prompt("code_generation")
        code = self.llm.complete(
            prompt=f"Design Package:\n\n{state.get('design_package', '')}",
            system=system,
        )
        state["generated_code"] = code
        state["workflow_status"] = "code_generated"
        return state
