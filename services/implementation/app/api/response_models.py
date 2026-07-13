"""Response models for the implementation API."""

from pydantic import BaseModel


class StartResponse(BaseModel):
    project_id: str
    workflow_status: str
    generated_code: str | None = None
