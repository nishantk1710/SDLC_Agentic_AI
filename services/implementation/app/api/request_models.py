"""Request models for the implementation API."""

from pydantic import BaseModel


class StartRequest(BaseModel):
    project_id: str
    design_package: str
