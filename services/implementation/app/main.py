"""FastAPI entrypoint for the Implementation Service.

FastAPI exposes the REST API and delegates to the LangGraph workflow.
It contains no agent logic itself.
"""

import logging

from fastapi import FastAPI

from app.api.routes import router
from app.config.settings import get_settings

settings = get_settings()

logging.basicConfig(level=settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.app_name}
