"""
syntax_check.py — confirms a generated file is syntactically valid before
it's ever handed to Step D for execution.

Dispatches by file extension:
  - .py            -> ast.parse(), always available, always exact.
  - .js             -> shells out to `node --check` if a `node` binary is on
                       PATH; skipped with a warning otherwise (matching the
                       pattern used elsewhere in this module for external
                       dependencies that can't be assumed always present).
  - .jsx/.ts/.tsx   -> NOT checked. JSX needs a transform (Babel/TS) Node's
                       own parser doesn't do, and TS needs a type-stripping
                       step; this module doesn't carry either as a
                       dependency. This is an honest, logged gap, not a
                       silently-passed check -- do not read "no errors" for
                       these files as "verified valid."
"""

import ast
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from codegen.base_generator import GeneratedFile

logger = logging.getLogger(__name__)

_UNCHECKED_EXTENSIONS = (".jsx", ".ts", ".tsx")


def check_syntax(generated_file: GeneratedFile) -> list[str]:
    """Returns a list of error strings; empty means either the code parses,
    or (for extensions we can't check) the check was skipped -- see the
    module docstring for exactly which is which."""
    path = generated_file.file_path
    if path.endswith(".py"):
        return _check_python(generated_file)
    if path.endswith(".js"):
        return _check_js_via_node(generated_file)
    if path.endswith(_UNCHECKED_EXTENSIONS):
        logger.warning(
            "%s: syntax not checked (JSX/TS need a parser this module doesn't carry) -- "
            "generated but unverified",
            path,
        )
        return []
    return [f"{path}: no syntax checker for this file type"]


def _check_python(generated_file: GeneratedFile) -> list[str]:
    try:
        ast.parse(generated_file.code)
    except SyntaxError as e:
        return [f"{generated_file.file_path}: syntax error: {e}"]
    return []


def _check_js_via_node(generated_file: GeneratedFile) -> list[str]:
    node_bin = shutil.which("node")
    if node_bin is None:
        logger.warning(
            "%s: 'node' binary not found on PATH -- skipping JS syntax check",
            generated_file.file_path,
        )
        return []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(generated_file.code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [node_bin, "--check", tmp_path],
            capture_output=True, text=True, timeout=10,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        return [f"{generated_file.file_path}: syntax error: {result.stderr.strip()}"]
    return []
