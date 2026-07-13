"""REST API routes. FastAPI validates the request and calls the LangGraph
workflow; it contains no agent logic itself.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.request_models import StartRequest
from app.api.response_models import StartResponse
from app.graph.graph import workflow
from app.graph.state import WorkflowState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/implementation", tags=["implementation"])


@router.post("/start", response_model=StartResponse)
def start(request: StartRequest) -> StartResponse:
    """Run the implementation workflow for a design package."""
    initial: WorkflowState = {
        "project_id": request.project_id,
        "design_package": request.design_package,
        "workflow_status": "started",
    }
    # The workflow makes synchronous LLM calls; surface failures as a clean
    # 502 instead of a raw 500. TODO: move to background execution + a
    # GET /status/{project_id} endpoint once the pipeline grows.
    try:
        result = workflow.invoke(initial)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Workflow failed for project %s", request.project_id)
        raise HTTPException(
            status_code=502, detail="Implementation workflow failed"
        ) from exc
    return StartResponse(
        project_id=result["project_id"],
        workflow_status=result.get("workflow_status", "completed"),
        generated_code=result.get("generated_code"),
    )
