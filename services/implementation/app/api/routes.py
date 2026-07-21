"""REST API routes. FastAPI validates the request and calls the LangGraph
workflow; it contains no agent logic itself.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.api.request_models import RefactorRequest, StartRequest
from app.api.response_models import RefactorResponse, StartResponse
from app.graph.graph import refactor_workflow, workflow
from app.graph.state import WorkflowState, new_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/implementation", tags=["implementation"])


@router.post("/start", response_model=StartResponse)
def start(request: StartRequest) -> StartResponse:
    """Run the implementation workflow for a design package."""
    run_id = uuid4().hex
    initial: WorkflowState = new_state(
        run_id=run_id,
        attempt=request.attempt,
        project_id=request.project_id,
        design_package=request.design_package,
    )
    initial["workflow_status"] = "started"

    # The graph is compiled with a checkpointer (for the HITL interrupt), so invoke needs a
    # thread id. The workflow makes synchronous LLM calls; surface failures as a clean 502.
    # TODO: move to background execution + GET /status/{project_id} once the pipeline grows.
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 100}
    try:
        workflow.invoke(initial, config)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Workflow failed for project %s", request.project_id)
        raise HTTPException(status_code=502, detail="Implementation workflow failed") from exc

    # Read the current state (also correct when the run paused at the human-review interrupt).
    final = workflow.get_state(config).values
    return StartResponse(
        project_id=final.get("project_id", request.project_id),
        workflow_status=final.get("workflow_status", "completed"),
        run_id=final.get("run_id", run_id),
        generated_code=final.get("generated_code") or [],
    )


@router.post("/refactor", response_model=RefactorResponse)
def refactor(request: RefactorRequest) -> RefactorResponse:
    """Apply a code-review report's findings to the code in the sandbox (standalone entry).

    Reads the report (its ``Repository:`` URL + findings), ensures the code is in the sandbox
    (clones the report's repository when the workspace is empty), applies each finding, and returns
    a summary. Requires a connected exec-sandbox executor.
    """
    run_id = uuid4().hex
    initial: WorkflowState = new_state(
        run_id=run_id, attempt=request.attempt, project_id=request.project_id or ""
    )
    initial["review_report"] = request.review_report
    initial["workflow_status"] = "refactor_requested"

    try:
        final = refactor_workflow.invoke(initial)
    except RuntimeError as exc:  # no executor configured — the exec-sandbox is not connected
        logger.exception("Refactor failed: executor unavailable")
        raise HTTPException(status_code=503, detail="exec-sandbox not connected") from exc
    except Exception as exc:  # noqa: BLE001 - surface any run failure as a clean 502
        logger.exception("Refactor workflow failed for project %s", request.project_id)
        raise HTTPException(status_code=502, detail="Refactor workflow failed") from exc

    return RefactorResponse(
        project_id=final.get("project_id", request.project_id or ""),
        workflow_status=final.get("workflow_status", "refactored"),
        run_id=final.get("run_id", run_id),
        refactored_code=final.get("refactored_code", ""),
    )
