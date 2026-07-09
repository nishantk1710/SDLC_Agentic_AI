"""REST API routes. FastAPI validates the request and calls the LangGraph
workflow; it contains no agent logic itself.
"""

from fastapi import APIRouter

from app.api.request_models import StartRequest
from app.api.response_models import StartResponse
from app.graph.graph import workflow
from app.graph.state import WorkflowState

router = APIRouter(prefix="/implementation", tags=["implementation"])


@router.post("/start", response_model=StartResponse)
def start(request: StartRequest) -> StartResponse:
    """Run the implementation workflow for a design package."""
    initial: WorkflowState = {
        "project_id": request.project_id,
        "design_package": request.design_package,
        "workflow_status": "started",
    }
    result = workflow.invoke(initial)
    return StartResponse(
        project_id=result["project_id"],
        workflow_status=result.get("workflow_status", "completed"),
        generated_code=result.get("generated_code"),
    )
