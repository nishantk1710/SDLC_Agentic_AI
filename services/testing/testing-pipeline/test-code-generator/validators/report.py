"""
report.py — runs every validator against each generated file and splits
them into passed/rejected. Anything that fails any check is quarantined,
never silently written to the main output.
"""

from pydantic import BaseModel

from codegen.base_generator import GeneratedFile
from schema import TestCase
from validators.import_check import check_imports
from validators.syntax_check import check_syntax
from validators.traceability_check import check_traceability


class FileValidationResult(BaseModel):
    file_path: str
    passed: bool
    errors: list[str]


class ValidationReport(BaseModel):
    results: list[FileValidationResult]

    @property
    def passed_files(self) -> list[str]:
        return [r.file_path for r in self.results if r.passed]

    @property
    def rejected_files(self) -> list[str]:
        return [r.file_path for r in self.results if not r.passed]


def validate_generated_files(
    generated_files: list[GeneratedFile], all_cases: list[TestCase]
) -> tuple[list[GeneratedFile], list[GeneratedFile], ValidationReport]:
    """Runs every validator against every generated file. Returns
    (passed, rejected, report)."""
    cases_by_id = {c.id: c for c in all_cases}

    passed: list[GeneratedFile] = []
    rejected: list[GeneratedFile] = []
    results: list[FileValidationResult] = []

    for gf in generated_files:
        errors: list[str] = []
        errors.extend(check_syntax(gf))
        errors.extend(check_imports(gf))
        errors.extend(check_traceability(gf, cases_by_id))

        ok = not errors
        results.append(FileValidationResult(file_path=gf.file_path, passed=ok, errors=errors))
        (passed if ok else rejected).append(gf)

    return passed, rejected, ValidationReport(results=results)
