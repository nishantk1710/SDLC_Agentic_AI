"""Testing Phase entrypoint & pipeline orchestrator (Team 4).

One FastAPI app for the whole testing phase, and the single seam where every
stage integrates into one seamless pipeline. A single API — ``POST /run`` —
executes the pipeline end to end and returns one combined result.

Pipeline stages (reference §1: linear A -> B -> C -> D1/D2 -> E -> F, preceded
by source loading):

    Stage 0  Source Loader Service   fetch source code + SRS + design   [DONE]
    Stage A  Interface Extraction    chunk -> mapping tree -> strategy   [DONE]
    Stage B  Test-Case Derivation    requirements -> test_cases.json     [DONE]
    Stage C  Test Code Generation    templates -> test code              [TODO]
    Stage D  Execution (D1 / D2)     run tests (main + sidecar)          [TODO]
    Stage E  Result Mapping + Report join results -> report              [TODO]
    Stage F  Verdict                 PASS / FAIL / ERROR                 [TODO]

As each stage is built it is appended to ``run_pipeline`` below — the API and
its response envelope stay stable. The Source Loader Service runs **in-process**
(reference §1 — it is a module of the testing phase, not a networked service);
it is a flat set of modules in a hyphenated folder, so it cannot be imported as
a package — we put its directory on ``sys.path`` and import its functions.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parent / "testing-pipeline"
_SOURCE_LOADER_DIR = Path(__file__).resolve().parent / "source-loader-service"
_INTERFACE_EXTRACTION_DIR = _PIPELINE_DIR / "interface-extraction"
_TEST_CASE_DERIVATION_DIR = _PIPELINE_DIR / "test-case-derivation"
sys.path.append(str(_SOURCE_LOADER_DIR))
sys.path.append(str(_INTERFACE_EXTRACTION_DIR))
sys.path.append(str(_TEST_CASE_DERIVATION_DIR))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from artifact_loader import load_design, load_srs  # noqa: E402
from exceptions import SourceLoadError  # noqa: E402
from source_loader import load_source  # noqa: E402

# Stages A/B — flat modules on sys.path with unique names so they do not collide
# with each other or the Source Loader Service's modules.
from interface_extraction import run_interface_extraction  # noqa: E402
from test_case_derivation import run_test_case_derivation  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Testing Phase Pipeline", version="0.1.0")


def run_pipeline() -> dict:
    """Execute the testing pipeline and return one combined result.

    Today this runs Stage 0 (source loading) and Stage A (interface extraction);
    stages B–F are appended here as they are built, feeding the ``verdict`` this
    eventually returns.
    """
    # --- Stage 0: Source Loader Service (in-process) ---
    source = load_source()
    srs = load_srs()
    design = load_design()
    logger.info(
        "Stage 0 (source loading) OK: source=%d, srs=%d, design=%d files",
        source.file_count,
        srs.file_count,
        design.file_count,
    )

    # --- Stage A: Interface Extraction (chunk -> mapping tree -> strategy) ---
    # Reads the source loader's output tree; writes chunks / mapping-tree /
    # strategy under data/. A3 degrades to an empty-but-valid strategy if no LLM
    # is configured, so this never breaks the pipeline.
    interface = run_interface_extraction()
    logger.info("Stage A (interface extraction) OK: %s", interface["summary"])

    # --- Stage B: Test-Case Derivation (strategy -> concrete test cases) ---
    # Consumes Stage A's outputs in-memory; writes data/test-cases.json. Uses the
    # ZenseAI MCP tool if configured, else the direct-LLM planner (POC default).
    ia_data = interface["data"]
    derivation = run_test_case_derivation(
        requirements=ia_data["requirements"],
        mapping_tree=ia_data["mapping_tree"],
        strategy=ia_data["test_strategy"],
        tech_stack=ia_data["tech_stack"],
    )
    logger.info("Stage B (test-case derivation) OK: %s", derivation["summary"])

    # --- Stages C–F slot in here as they are implemented ---

    return {
        "status": "OK",
        "stage": "test-case-derivation",
        "inputs": {
            "source_code": source.model_dump(),
            "srs": srs.model_dump(),
            "design": design.model_dump(),
        },
        "interface_extraction": {
            "summary": interface["summary"],
            "artifacts": interface["artifacts"],
        },
        "test_case_derivation": {
            "summary": derivation["summary"],
            "artifacts": derivation["artifacts"],
        },
        # "verdict": ...  # produced by Stage F once the pipeline is complete
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
def run() -> JSONResponse:
    """Run the testing pipeline. Currently executes the Source Loader Service
    (source code + SRS + design artifact). A source-loading failure returns an
    ``ERROR`` response — the pipeline's ERROR verdict path."""
    try:
        result = run_pipeline()
    except SourceLoadError as exc:
        logger.error("Pipeline failed at source loading [%s]: %s", exc.code, exc)
        return JSONResponse(
            status_code=422,
            content={
                "status": "ERROR",
                "stage": "source-loading",
                "error_code": exc.code,
                "error_message": exc.message,
            },
        )
    return JSONResponse(status_code=200, content=result)
