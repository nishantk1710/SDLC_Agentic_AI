"""
import_check.py — statically verifies every non-stdlib, non-framework
import in a generated file resolves against the real source tree, catching
a hallucinated import path (e.g. a module name the LLM invented) before
Step D ever tries to run the file.

Source tree location defaults to services/testing/data/unzipped/, where the
Source Loader Service extracts the orchestrator's zip artifact. If that
directory doesn't exist yet (current state -- Source Loader hasn't run),
this check is skipped with a warning rather than failing the whole
validation run.

Python: real check -- resolves dotted module names against .py files/packages.

JS/JSX/TS/TSX: NOT implemented yet, deliberately. JS test imports are
typically relative ("../app", "../LoginForm"), and resolving those
correctly requires knowing where the generated test file will actually sit
relative to the real source tree -- a placement decision nobody's made yet.
Rather than guess and risk false positives/negatives, this is an honest,
logged gap (same pattern as syntax_check.py's JSX/TS gap), not a
fabricated check.
"""

import ast
import logging
from pathlib import Path

from codegen.base_generator import GeneratedFile

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_ROOT = Path("services/testing/data/unzipped")

# Known third-party/stdlib/test-framework roots -- never "the code under
# test", so imports rooted at these are never flagged.
_KNOWN_EXTERNAL_ROOTS = {
    "fastapi", "starlette", "pytest", "httpx", "anthropic", "pydantic",
    "json", "os", "sys", "typing", "collections", "pathlib", "uuid",
    "unittest", "datetime", "re", "logging", "abc", "itertools",
}

_JS_LIKE_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx")


def check_imports(generated_file: GeneratedFile, source_root: Path = DEFAULT_SOURCE_ROOT) -> list[str]:
    """Returns a list of error strings; empty means every import resolved,
    the source tree isn't available yet, or (for JS-like files) the check
    isn't implemented yet -- see module docstring for which is which."""
    path = generated_file.file_path
    if path.endswith(_JS_LIKE_EXTENSIONS):
        logger.info(
            "%s: import resolution not implemented for JS/TS yet (relative-path "
            "placement isn't decided) -- skipped, not verified",
            path,
        )
        return []

    if not source_root.exists():
        logger.warning(
            "%s not found; skipping import resolution check (Source Loader hasn't run yet)",
            source_root,
        )
        return []

    tree = ast.parse(generated_file.code)
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                errors.extend(_check_module(alias.name, source_root))
        elif isinstance(node, ast.ImportFrom) and node.module:
            errors.extend(_check_module(node.module, source_root))
    return errors


def _check_module(dotted_name: str, source_root: Path) -> list[str]:
    top_level = dotted_name.split(".")[0]
    if top_level in _KNOWN_EXTERNAL_ROOTS:
        return []
    if _resolve(dotted_name, source_root):
        return []
    return [f"import {dotted_name!r} does not resolve under {source_root}"]


def _resolve(dotted_name: str, source_root: Path) -> bool:
    parts = dotted_name.split(".")
    candidate = source_root.joinpath(*parts)
    return candidate.with_suffix(".py").exists() or (candidate / "__init__.py").exists()
