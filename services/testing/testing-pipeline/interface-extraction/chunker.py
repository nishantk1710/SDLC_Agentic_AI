"""A1 — Codebase chunking (symbol-level).

Turns ``source_code[]`` into one chunk per symbol (class / function / method)
— NOT file-level blobs — so each chunk becomes a node in the A2 mapping tree.
This is the opposite of a RAG-style file-summary chunker; we keep call-graph
structure intact.

POC scope
---------
* **Python** is parsed with the standard-library ``ast`` module (deterministic,
  zero external dependencies) — the canonical, most-accurate Python parser.
* **JavaScript / TypeScript** are parsed with **tree-sitter** (see
  :mod:`tree_sitter_parsers`), matching the reference-doc's polyglot intent.
* Any other language (e.g. Java until its grammar is registered) falls back to
  :mod:`llm_fallback`'s coarse text splitter. Adding a language = registering a
  parser in ``_PARSERS`` — nothing else changes.

Each chunk::

    {
      "symbol_id": "app/user.py::UserService.create_user",
      "filename": "app/user.py",
      "language": "python",
      "symbol_type": "method",          # class | function | method | chunk
      "signature": "create_user(self, name, age)",
      "content": "def create_user(...): ...",
      "start_line": 12, "end_line": 18,
      "calls": ["validate_age", "save"], # raw callee names; A2 resolves these
      "is_test": false
    }
"""

from __future__ import annotations

import ast
import os
from typing import Callable, Dict, List, Optional

from logger import get_logger
from fallback_chunker import fallback_chunk_file

logger = get_logger(__name__)

Chunk = Dict[str, object]
ParserFn = Callable[[str, str], List[Chunk]]

_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
}


# ---------------------------------------------------------------------------
# test-file detection (adapted from the reference planner's _is_test_file)
# ---------------------------------------------------------------------------
def is_test_file(filename: str) -> bool:
    if not filename:
        return False
    lower = filename.lower().replace("\\", "/")
    base = lower.rsplit("/", 1)[-1]
    return any(
        [
            "/test/" in lower,
            "/tests/" in lower,
            base.startswith("test_"),
            base.endswith("_test.py"),
            base.endswith(".test.js"),
            base.endswith(".test.ts"),
            base.endswith(".test.tsx"),
            base.endswith(".spec.js"),
            base.endswith(".spec.ts"),
            base.endswith(".spec.tsx"),
            base.endswith("test.java"),
        ]
    )


# ---------------------------------------------------------------------------
# Python AST parser (A1 for runtime=python)
# ---------------------------------------------------------------------------
def _callee_name(func: ast.AST) -> Optional[str]:
    """Best-effort short name of a call target.

    ``foo()``        -> "foo"      (ast.Name)
    ``obj.bar()``    -> "bar"      (ast.Attribute — we keep the attribute)
    anything else    -> None
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _exc_name(exc: ast.AST) -> Optional[str]:
    """Short name of the exception in a ``raise <exc>`` statement."""
    if isinstance(exc, ast.Call):
        return _callee_name(exc.func)
    if isinstance(exc, ast.Name):
        return exc.id
    if isinstance(exc, ast.Attribute):
        return exc.attr
    return None


def _extract_calls_and_raises(node: ast.AST, skip_nested_defs: bool):
    """Return ``(calls, raises)`` inside ``node``.

    A ``raise Foo(...)`` contributes ``Foo`` to *raises*, not *calls* — so
    exception constructors no longer pollute the call graph (this also removes
    the old false ``validate_age -> AgeValidationError`` style edge). When
    ``skip_nested_defs`` is set we do not descend into nested function/class
    definitions (used for a *class* chunk so it doesn't absorb its methods').
    """
    calls: List[str] = []
    raises: List[str] = []
    # Don't count this symbol's own decorators (e.g. @app.post("/x")) as calls.
    skip_ids = {id(d) for d in getattr(node, "decorator_list", [])}

    def rec(n: ast.AST) -> None:
        for child in ast.iter_child_nodes(n):
            if id(child) in skip_ids:
                continue
            if skip_nested_defs and isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            if isinstance(child, ast.Raise):
                if child.exc is not None:
                    nm = _exc_name(child.exc)
                    if nm:
                        raises.append(nm)
                    # recurse into the raise EXCEPT its exception node, so the
                    # exception constructor isn't also counted as a call
                    for sub in ast.iter_child_nodes(child):
                        if sub is not child.exc:
                            rec(sub)
                continue
            if isinstance(child, ast.Call):
                nm = _callee_name(child.func)
                if nm:
                    calls.append(nm)
            rec(child)

    rec(node)
    return _dedup(calls), _dedup(raises)


def _dedup(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _func_signature(node: ast.AST, name: str) -> str:
    try:
        args = ast.unparse(node.args)  # type: ignore[attr-defined]
    except Exception:
        args = ""
    return f"{name}({args})"


def _class_signature(node: ast.ClassDef) -> str:
    try:
        bases = ", ".join(ast.unparse(b) for b in node.bases)
    except Exception:
        bases = ""
    return f"class {node.name}({bases})" if bases else f"class {node.name}"


def _content_of(source: str, node: ast.AST) -> str:
    try:
        seg = ast.get_source_segment(source, node)
        if seg is not None:
            return seg
    except Exception:
        pass
    # Fallback: slice by line numbers.
    lines = source.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", start + 1)
    return "\n".join(lines[start:end])


# HTTP verbs used as decorator attributes by FastAPI/Starlette/Flask routers.
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _decorator_text(dec: ast.AST) -> str:
    try:
        return ast.unparse(dec)
    except Exception:
        return ""


def _parse_route(dec: ast.AST):
    """Detect an HTTP route decorator -> ``(method, path)`` or ``(None, None)``.

    Handles FastAPI/Starlette (``@app.post("/x")``, ``@router.get("/x")``) and
    Flask (``@app.route("/x", methods=["POST"])``).
    """
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None, None
    attr = dec.func.attr.lower()
    path = None
    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
        path = dec.args[0].value
    if attr in _HTTP_METHODS:
        return attr.upper(), path
    if attr == "route":  # Flask-style: method(s) in a keyword
        method = "GET"
        for kw in dec.keywords:
            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                vals = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                if vals:
                    method = str(vals[0]).upper()
        return method, path
    return None, None


def _endpoint_info(node: ast.AST):
    """Return ``(decorators, is_endpoint, http_method, route)`` for a def node."""
    decorators = [_decorator_text(d) for d in getattr(node, "decorator_list", [])]
    for dec in getattr(node, "decorator_list", []):
        method, path = _parse_route(dec)
        if method:
            return decorators, True, method, path
    return decorators, False, None, None


def chunk_python_source(path: str, content: str) -> List[Chunk]:
    """Parse one Python file into symbol-level chunks."""
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        logger.warning("A1: could not parse %s (%s); using fallback", path, exc)
        return fallback_chunk_file(path, content, language="python")

    test_flag = is_test_file(path)
    chunks: List[Chunk] = []

    def emit(node, symbol_type: str, qualname: str, signature: str, skip_nested: bool):
        calls, raises = _extract_calls_and_raises(node, skip_nested_defs=skip_nested)
        decorators, is_endpoint, http_method, route = _endpoint_info(node)
        chunks.append(
            {
                "symbol_id": f"{path}::{qualname}",
                "filename": path,
                "language": "python",
                "symbol_type": symbol_type,
                "signature": signature,
                "content": _content_of(content, node),
                "start_line": getattr(node, "lineno", None),
                "end_line": getattr(node, "end_lineno", None),
                "calls": calls,
                "raises": raises,           # exception types raised (from `raise X(...)`)
                "decorators": decorators,   # decorator source strings
                "is_endpoint": is_endpoint,  # HTTP route decorator present
                "http_method": http_method,  # e.g. "POST" (None if not an endpoint)
                "route": route,              # e.g. "/api/checkout" (None if not an endpoint)
                "is_test": test_flag,
            }
        )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            emit(node, "function", node.name, _func_signature(node, node.name), skip_nested=False)
        elif isinstance(node, ast.ClassDef):
            # Class node itself (calls only from class-level statements).
            emit(node, "class", node.name, _class_signature(node), skip_nested=True)
            # Each method is its own chunk/node.
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qual = f"{node.name}.{sub.name}"
                    emit(sub, "method", qual, _func_signature(sub, sub.name), skip_nested=False)

    return chunks


# ---------------------------------------------------------------------------
# Parser registry + public entry point
# ---------------------------------------------------------------------------
def _tree_sitter_parser(language: str) -> ParserFn:
    """Wrap the tree-sitter JS/TS parser; fall back to the coarse splitter if
    the grammar wheels aren't installed (keeps the Python-only path dependency
    free and never crashes)."""

    def _parse(path: str, content: str) -> List[Chunk]:
        from tree_sitter_parsers import chunk_with_tree_sitter

        chunks = chunk_with_tree_sitter(path, content, language, is_test_file(path))
        if chunks is None:
            logger.info("A1: tree-sitter grammar unavailable for %s (%s); using fallback", language, path)
            return fallback_chunk_file(path, content, language=language)
        return chunks

    return _parse


_PARSERS: Dict[str, ParserFn] = {
    "python": chunk_python_source,              # stdlib ast (best tool for Python)
    "javascript": _tree_sitter_parser("javascript"),   # tree-sitter
    "typescript": _tree_sitter_parser("typescript"),   # tree-sitter (+ tsx variant)
    # Add more tree-sitter languages the same way (e.g. "java") once their
    # grammar wheel is installed.
}


def _detect_language(item: Dict[str, str]) -> str:
    lang = (item.get("language") or "").strip().lower()
    if lang:
        return lang
    _, ext = os.path.splitext(item.get("path", ""))
    return _EXT_TO_LANG.get(ext.lower(), "")


def chunk_codebase(
    source_code: List[Dict[str, str]],
    tech_stack: Optional[Dict[str, str]] = None,
) -> List[Chunk]:
    """A1 entry point: ``source_code[]`` -> ``chunks[]`` (symbol-level).

    Each ``source_code`` item is ``{"path", "language", "content"}``. Files in
    a language without a registered parser fall back to a coarse text splitter
    so nothing is silently dropped.
    """
    all_chunks: List[Chunk] = []
    for item in source_code or []:
        path = item.get("path", "<unknown>")
        content = item.get("content", "") or ""
        language = _detect_language(item)
        parser = _PARSERS.get(language)
        if parser is None:
            logger.info("A1: no parser for language=%r (%s); using fallback", language, path)
            all_chunks.extend(fallback_chunk_file(path, content, language=language or "unknown"))
            continue
        all_chunks.extend(parser(path, content))

    logger.info("A1: produced %d chunk(s) from %d file(s)", len(all_chunks), len(source_code or []))
    return all_chunks
