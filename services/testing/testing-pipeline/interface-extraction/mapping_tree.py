"""A2 — Codebase mapping tree.

Assembles A1's ``chunks[]`` into a ``symbol_id``-keyed graph with ``calls`` /
``called_by`` edges — the call/dependency tree. Deterministic: pure graph
assembly, no LLM.

Call resolution (POC)
---------------------
A1 records raw callee *short names* (e.g. ``validate_age``, ``save``). Here we
resolve them to concrete ``symbol_id``s by matching against known symbols'
short names:

* resolved  -> internal edge in ``calls`` / ``called_by``
* unresolved (stdlib, third-party, ``self.repo.save``, ...) -> kept on the
  node as ``external_calls`` so nothing is invented.

Ambiguous names (same short name in two files) link to all candidates; that's
acceptable for the POC and easy to tighten later with real scope resolution.

Output shape (``mapping_tree``)::

    {
      "schema_version": "1.0",
      "symbols": { "<symbol_id>": { ...node... }, ... },
      "edges": [ {"from": "<id>", "to": "<id>"}, ... ],
      "stats": {"symbol_count": N, "edge_count": M, "file_count": F}
    }
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from logger import get_logger

logger = get_logger(__name__)

Chunk = Dict[str, object]
MappingTree = Dict[str, object]


def _short_name(symbol_id: str) -> str:
    """Last path component of a symbol id, e.g. 'a/b.py::C.m' -> 'm'."""
    tail = symbol_id.split("::", 1)[-1]
    return tail.split(".")[-1]


def build_mapping_tree(chunks: List[Chunk]) -> MappingTree:
    """A2 entry point: ``chunks[]`` -> mapping tree (JSON-serializable)."""
    symbols: Dict[str, dict] = {}
    name_index: Dict[str, List[str]] = defaultdict(list)

    # Pass 1: register every symbol as a node (content dropped to keep the
    # tree light; signatures/metadata are what downstream steps need).
    for ch in chunks:
        sid = ch["symbol_id"]
        symbols[sid] = {
            "symbol_id": sid,
            "filename": ch.get("filename"),
            "language": ch.get("language"),
            "symbol_type": ch.get("symbol_type"),
            "signature": ch.get("signature", ""),
            "start_line": ch.get("start_line"),
            "end_line": ch.get("end_line"),
            "is_test": ch.get("is_test", False),
            # A1 interface signals (used by A3 to classify test type / risk)
            "is_endpoint": ch.get("is_endpoint", False),
            "http_method": ch.get("http_method"),
            "route": ch.get("route"),
            "raises": ch.get("raises", []) or [],
            "calls": [],           # resolved internal targets
            "called_by": [],       # reverse edges
            "external_calls": [],  # unresolved callee names
        }
        name_index[_short_name(sid)].append(sid)

    # Pass 2: resolve raw call names to symbol ids and wire edges.
    edges: List[Dict[str, str]] = []
    for ch in chunks:
        sid = ch["symbol_id"]
        node = symbols[sid]
        for raw in ch.get("calls", []) or []:
            targets = [t for t in name_index.get(raw, []) if t != sid]
            if not targets:
                if raw not in node["external_calls"]:
                    node["external_calls"].append(raw)
                continue
            for tgt in targets:
                if tgt not in node["calls"]:
                    node["calls"].append(tgt)
                    edges.append({"from": sid, "to": tgt})
                if sid not in symbols[tgt]["called_by"]:
                    symbols[tgt]["called_by"].append(sid)

    # Per-node graph metrics (F3): fan_in = number of callers (blast radius),
    # fan_out = number of resolved internal callees.
    for node in symbols.values():
        node["fan_in"] = len(node["called_by"])
        node["fan_out"] = len(node["calls"])

    file_count = len({s.get("filename") for s in symbols.values()})
    tree: MappingTree = {
        "schema_version": "1.0",
        "symbols": symbols,
        "edges": edges,
        "stats": {
            "symbol_count": len(symbols),
            "edge_count": len(edges),
            "file_count": file_count,
        },
    }
    logger.info(
        "A2: mapping tree with %d symbol(s), %d edge(s)",
        len(symbols),
        len(edges),
    )
    return tree
