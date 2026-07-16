"""
output_writer.py — writes validated generated files + a manifest to
services/testing/data/generated_tests/<run_id>/.

Only files that passed validation are written into the main output tree;
rejected files are quarantined under a rejected/ subfolder instead, never
mixed in with passing tests -- per the plan's guardrail requirement that a
bad file must be visibly separated, not silently indistinguishable from a
good one. validation_report.json is written alongside so a rejection's
reason is always inspectable without re-running validation.
"""

from pathlib import Path

from pydantic import BaseModel

from codegen.base_generator import GeneratedFile
from validators.report import ValidationReport

DEFAULT_OUTPUT_ROOT = Path("services/testing/data/generated_tests")


class ManifestEntry(BaseModel):
    file_path: str
    runner: str
    source_test_case_ids: list[str]
    req_ids: list[str]


class Manifest(BaseModel):
    run_id: str
    generated_files: list[ManifestEntry]
    validation_report_ref: str
    generation_errors: list[str] = []


def write_output(
    run_id: str,
    passed: list[GeneratedFile],
    rejected: list[GeneratedFile],
    report: ValidationReport,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    generation_errors: list[str] | None = None,
) -> Path:
    """Writes passed files, quarantines rejected files, and writes
    manifest.json + validation_report.json. Returns the run directory.

    generation_errors carries routing-key-level failures from
    dispatcher.dispatch() (e.g. a project's React cases skipped because
    that generator isn't implemented yet) -- these are a DIFFERENT thing
    from `rejected`, which is validator failures on files that WERE
    generated. Both get surfaced, neither is silently dropped."""
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    for gf in passed:
        _write_generated_file(run_dir, gf)

    if rejected:
        rejected_dir = run_dir / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        for gf in rejected:
            _write_generated_file(rejected_dir, gf)

    manifest = Manifest(
        run_id=run_id,
        generated_files=[
            ManifestEntry(
                file_path=gf.file_path,
                runner=gf.runner,
                source_test_case_ids=gf.source_test_case_ids,
                req_ids=gf.req_ids,
            )
            for gf in passed
        ],
        validation_report_ref="validation_report.json",
        generation_errors=generation_errors or [],
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    (run_dir / "validation_report.json").write_text(report.model_dump_json(indent=2))

    return run_dir


def _write_generated_file(base_dir: Path, gf: GeneratedFile) -> None:
    path = base_dir / gf.file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gf.code)
