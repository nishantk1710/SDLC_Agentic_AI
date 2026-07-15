"""A1 symbol extraction for JS/TS via tree-sitter (polyglot arm of the chunker).

Why tree-sitter here (and NOT for Python): Python is parsed with the stdlib
``ast`` module (see ``codebase_chunker.chunk_python_source``) because that is
the canonical, dependency-free, most-accurate Python parser. tree-sitter's
value is *polyglot* coverage, so we use it for the languages ``ast`` cannot
handle — JavaScript and TypeScript here.

Offline by design: grammars come from the ``tree-sitter-javascript`` /
``tree-sitter-typescript`` wheels (compiled grammar bundled in the wheel). No
runtime download — important for the later network-disabled sandbox. If the
wheels are not installed, ``chunk_with_tree_sitter`` returns ``None`` and the
caller falls back to the coarse splitter, so nothing crashes.

Produces the SAME chunk schema as the Python parser, so A2/A3 are unchanged.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from logger import get_logger

logger = get_logger(__name__)

Chunk = Dict[str, object]

# Nested definition node types we do NOT descend into when collecting a
# container's own calls (so a class's calls don't absorb its methods' calls).
_DEF_TYPES = {
    "function_declaration",
    "function_expression",
    "arrow_function",
    "method_definition",
    "class_declaration",
}

_PARSER_CLS = None          # tree_sitter.Parser class (once loaded)
_LANGS: Optional[Dict[str, object]] = None  # language_key -> Language
_LOADED = False


def _ensure_loaded() -> None:
    """Lazy, cached load of tree-sitter core + grammars. Never raises."""
    global _PARSER_CLS, _LANGS, _LOADED
    if _LOADED:
        return
    _LOADED = True
    langs: Dict[str, object] = {}
    try:
        from tree_sitter import Language, Parser
    except Exception as exc:  # tree-sitter not installed -> caller falls back
        logger.info("tree-sitter core not available (%s); JS/TS will use fallback", exc)
        _LANGS = langs
        return

    _PARSER_CLS = Parser
    try:
        import tree_sitter_javascript as tsjs
        langs["javascript"] = Language(tsjs.language())
    except Exception as exc:
        logger.info("tree-sitter-javascript unavailable (%s)", exc)
    try:
        import tree_sitter_typescript as tsts
        langs["typescript"] = Language(tsts.language_typescript())
        langs["tsx"] = Language(tsts.language_tsx())
    except Exception as exc:
        logger.info("tree-sitter-typescript unavailable (%s)", exc)

    _LANGS = langs


# ---------------------------------------------------------------------------
# small CST helpers
# ---------------------------------------------------------------------------
def _text(src: bytes, node) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _callee_name(src: bytes, func_node) -> Optional[str]:
    """Short name of a call target: identifier -> its text; obj.method -> method."""
    if func_node is None:
        return None
    if func_node.type == "identifier":
        return _text(src, func_node)
    if func_node.type == "member_expression":
        prop = func_node.child_by_field_name("property")
        if prop is not None:
            return _text(src, prop)
    return None


def _iter_calls(src: bytes, node, skip_nested: bool):
    """Yield callee short-names within ``node`` (like the Python chunker).

    ``new X()`` is a ``new_expression`` (constructor), not a ``call_expression``,
    so exception/constructor instantiation is naturally NOT counted as a call —
    a cleaner call graph than the Python side currently gets.
    """
    for child in node.children:
        if skip_nested and child.type in _DEF_TYPES:
            continue
        if child.type == "call_expression":
            name = _callee_name(src, child.child_by_field_name("function"))
            if name:
                yield name
        yield from _iter_calls(src, child, skip_nested)


def _dedup(seq) -> List[str]:
    seen, out = set(), []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _signature(src: bytes, name: str, node) -> str:
    params = node.child_by_field_name("parameters")
    if params is None:
        return f"{name}()"
    ptext = _text(src, params).strip()
    if not ptext.startswith("("):  # e.g. single-arg arrow `x => ...`
        ptext = f"({ptext})"
    return f"{name}{ptext}"


# ---------------------------------------------------------------------------
# symbol extraction
# ---------------------------------------------------------------------------
def _emit(chunks, src, path, language, is_test, node, symbol_type, qualname, signature, skip_nested):
    chunks.append(
        {
            "symbol_id": f"{path}::{qualname}",
            "filename": path,
            "language": language,
            "symbol_type": symbol_type,
            "signature": signature,
            "content": _text(src, node),
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "calls": _dedup(_iter_calls(src, node, skip_nested=skip_nested)),
            "is_test": is_test,
        }
    )


def _handle(node, chunks, src, path, language, is_test) -> None:
    t = node.type

    if t == "export_statement":  # unwrap `export function/class/const ...`
        for child in node.children:
            _handle(child, chunks, src, path, language, is_test)
        return

    if t == "function_declaration":
        nn = node.child_by_field_name("name")
        name = _text(src, nn) if nn else "<anon>"
        _emit(chunks, src, path, language, is_test, node, "function", name, _signature(src, name, node), skip_nested=False)

    elif t == "class_declaration":
        nn = node.child_by_field_name("name")
        cname = _text(src, nn) if nn else "<anon>"
        _emit(chunks, src, path, language, is_test, node, "class", cname, f"class {cname}", skip_nested=True)
        body = node.child_by_field_name("body")
        if body is not None:
            for m in body.children:
                if m.type == "method_definition":
                    mn = m.child_by_field_name("name")
                    mname = _text(src, mn) if mn else "<anon>"
                    _emit(chunks, src, path, language, is_test, m, "method",
                          f"{cname}.{mname}", _signature(src, mname, m), skip_nested=False)

    elif t in ("lexical_declaration", "variable_declaration"):
        # `const foo = (a) => {...}` / `const foo = function(){...}`
        for d in node.children:
            if d.type != "variable_declarator":
                continue
            val = d.child_by_field_name("value")
            if val is not None and val.type in ("arrow_function", "function_expression"):
                nn = d.child_by_field_name("name")
                fname = _text(src, nn) if nn else "<anon>"
                _emit(chunks, src, path, language, is_test, val, "function", fname, _signature(src, fname, val), skip_nested=False)

    elif t == "interface_declaration":  # TypeScript
        nn = node.child_by_field_name("name")
        iname = _text(src, nn) if nn else "<anon>"
        _emit(chunks, src, path, language, is_test, node, "interface", iname, f"interface {iname}", skip_nested=True)


def chunk_with_tree_sitter(
    path: str,
    content: str,
    language: str,
    is_test: bool,
) -> Optional[List[Chunk]]:
    """Parse a JS/TS file into symbol-level chunks, or ``None`` if unavailable."""
    _ensure_loaded()
    if not _LANGS:
        return None

    key = "tsx" if (language == "typescript" and path.endswith(".tsx")) else language
    lang = _LANGS.get(key) or _LANGS.get(language)
    if lang is None or _PARSER_CLS is None:
        return None

    parser = _PARSER_CLS(lang)
    src = content.encode("utf-8")
    tree = parser.parse(src)

    chunks: List[Chunk] = []
    for node in tree.root_node.children:
        _handle(node, chunks, src, path, language, is_test)
    return chunks
