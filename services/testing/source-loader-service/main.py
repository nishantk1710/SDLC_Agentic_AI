"""FastAPI surface for the Source Loader Service.

Endpoints:
  * ``GET  /health`` — liveness.
  * ``GET  /ready``  — readiness (the fixed zip source dir is reachable).
  * ``POST /load``   — fetch the zip from the fixed path and extract it; returns
    the manifest. A source-loading failure returns 422 with an ``ERROR`` body
    rather than a 500, mirroring the pipeline's ERROR verdict path.

Note: the reference design treats source loading as an in-process module of the
testing phase (not a networked service). This HTTP layer is a thin, testable
wrapper over ``load_source`` — the pipeline can call that function directly.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from artifact_loader import load_design, load_srs
from config import settings
from exceptions import SourceLoadError
from models import ArtifactLoadResult, LoadResult
from source_loader import load_source

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Source Loader Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    ok = settings.zip_source_dir.is_dir()
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "not_ready",
            "zip_source_dir": str(settings.zip_source_dir),
        },
    )


@app.post("/load", response_model=LoadResult)
def load() -> JSONResponse:
    try:
        result = load_source()
        return JSONResponse(status_code=200, content=result.model_dump())
    except SourceLoadError as exc:
        logging.getLogger(__name__).error("Source load failed [%s]: %s", exc.code, exc)
        result = LoadResult(
            status="ERROR", error_code=exc.code, error_message=exc.message
        )
        return JSONResponse(status_code=422, content=result.model_dump())


@app.post("/load-srs", response_model=ArtifactLoadResult)
def load_srs_endpoint() -> JSONResponse:
    try:
        result = load_srs()
        return JSONResponse(status_code=200, content=result.model_dump())
    except SourceLoadError as exc:
        logging.getLogger(__name__).error("SRS load failed [%s]: %s", exc.code, exc)
        result = ArtifactLoadResult(
            status="ERROR",
            artifact="SRS",
            error_code=exc.code,
            error_message=exc.message,
        )
        return JSONResponse(status_code=422, content=result.model_dump())


@app.post("/load-design", response_model=ArtifactLoadResult)
def load_design_endpoint() -> JSONResponse:
    try:
        result = load_design()
        return JSONResponse(status_code=200, content=result.model_dump())
    except SourceLoadError as exc:
        logging.getLogger(__name__).error("Design load failed [%s]: %s", exc.code, exc)
        result = ArtifactLoadResult(
            status="ERROR",
            artifact="design",
            error_code=exc.code,
            error_message=exc.message,
        )
        return JSONResponse(status_code=422, content=result.model_dump())
