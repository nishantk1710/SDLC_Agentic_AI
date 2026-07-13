"""Shared LangGraph workflow state.

Each agent receives this state, updates only the fields it owns, and returns it.
"""

from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    # Identity
    project_id: str

    # Inputs / artifacts (typically references to workspace paths)
    design_package: str
    generated_code: str
    review_report: str
    refactored_code: str
    unit_tests: str
    documentation: str
    security_report: str

    # Control
    workflow_status: str
