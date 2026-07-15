#!/usr/bin/env python3
"""
backend_structure.py  —  Level-3 Backend Structure agent

Consumes the Level-1/2 artifacts from the shared folder and produces the agreed
backend project layout:

    extracted_requirements.json   (tech stack + functional/non-functional needs)
    user_features.json            (features -> module boundaries)
    db_schema.json                (entities/collections/tables + datastore family)
    routes.json                   (OPTIONAL — frontend routes, for FE/BE alignment)
        ->  backend-structure.json        (nested folder tree, per handoff item #14)
            backend_structure_decision.md (approaches compared + chosen + why)

Reasoning style (same as the schema generator):
    1. DELIBERATE — study the stack, features and data model; propose 2-3
       genuinely different backend architectures with concrete pros/cons.
    2. DECIDE     — pick the best for THIS app and stack, with a rationale.
    3. GENERATE   — emit the concrete folder tree for the chosen architecture.

The tree is a nested JSON object: a folder maps to an object of children; a
leaf (folder or file) maps to a short purpose string. Example:
    {"src/": {"modules/": "feature modules", "controllers/": "route handlers",
              "services/": "business logic", "entities/": "DB entities",
              "dto/": "request/response shapes", "migrations/": "DB migrations"}}

Two entrypoints, one core:
    • CLI:        python backend_structure.py            (uses $SHARED_DIR)
    • LangGraph:  from backend_structure import backend_structure_node
                  graph.add_node("backend_structure", backend_structure_node)

Environment (shared with the other agents):
    SHARED_DIR          folder holding the inputs + where outputs go
    ANTHROPIC_API_KEY   Azure Foundry key
    ANTHROPIC_ENDPOINT  Foundry base URL (…/anthropic)
    DEFAULT_MODEL       deployment name (default 'claude-sonnet-5')
    ANTHROPIC_MAX_TOKENS  max tokens per call (default 8000)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("backend_structure")


def load_dotenv_files() -> None:
    """Load .env at import (optional dependency); real env vars win."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env", override=False)
    load_dotenv(override=False)


load_dotenv_files()

# ---------------------------------------------------------------------------
# Config (read from the environment, populated from .env above)
# ---------------------------------------------------------------------------
ENV_VAR = "SHARED_DIR"
MODEL = os.environ.get("DEFAULT_MODEL") or "claude-sonnet-5"
ANTHROPIC_ENDPOINT = os.environ.get("ANTHROPIC_ENDPOINT") or None
MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS") or "8000")

IN_REQUIREMENTS = "extracted_requirements.json"
IN_FEATURES = "user_features.json"
IN_SCHEMA = "db_schema.json"
IN_ROUTES = "routes.json"                    # frontend routes (optional, from FE initializer)

OUT_JSON = "backend-structure.json"
OUT_DECISION = "backend_structure_decision.md"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def resolve_shared_dir(cli_dir: str | None) -> Path:
    raw = cli_dir or os.environ.get(ENV_VAR)
    if not raw:
        raise SystemExit(f"No location set. Set {ENV_VAR} (the folder with the "
                         f"Level-1/2 artifacts) or pass --dir.")
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise SystemExit(f"{ENV_VAR} is not a directory: {p}")
    return p


def load_inputs(shared: Path) -> dict:
    def read(name: str, required: bool = True):
        f = shared / name
        if not f.is_file():
            if required:
                raise SystemExit(f"Missing input: {f}. Run the earlier agents first.")
            return None
        return json.loads(f.read_text(encoding="utf-8"))
    return {
        "extracted_requirements": read(IN_REQUIREMENTS),
        "user_features": read(IN_FEATURES),
        "db_schema": read(IN_SCHEMA),
        # Optional frontend artifact — used to align backend endpoints with the
        # frontend's routes when available; absent is fine.
        "routes": read(IN_ROUTES, required=False),
    }


def _extract_routes(routes) -> list:
    """Compact list of frontend routes, tolerant of shape.
    Accepts: a list of route objects/strings, a dict with a 'routes' list, or a
    path->meta mapping. Returns a small list the prompt can use to align backend
    endpoints with what the frontend actually navigates to."""
    if not routes:
        return []
    items = []
    if isinstance(routes, list):
        items = routes
    elif isinstance(routes, dict):
        if isinstance(routes.get("routes"), list):
            items = routes["routes"]
        else:                                   # treat as path -> meta mapping
            items = [{"path": k, **(v if isinstance(v, dict) else {})}
                     for k, v in routes.items()]
    out = []
    for r in items:
        if isinstance(r, str):
            out.append({"path": r})
        elif isinstance(r, dict):
            keep = {k: r[k] for k in ("path", "name", "component", "role", "roles",
                                      "method", "access", "protected") if k in r}
            if keep:
                out.append(keep)
    return out


def _extract_data_model(schema: dict) -> dict:
    """Derive the authoritative data SHAPE the backend must respect, so it never
    disagrees with the schema about where an entity's data physically lives.

    Returns:
      persisted_stores  — entities the schema persists as their OWN table/
                          collection. These are the only ones that get a
                          dedicated model + repository + (relational) migration.
      embedded_entities — entities the schema stores INSIDE a parent aggregate
                          (subdocuments/nested records). These must be accessed
                          through the parent; they get NO store of their own.

    Datastore-agnostic: relational tables never embed (embedded stays empty);
    document schemas expose subdocuments as embedded; native schemas fall back
    to the declared entity list.
    """
    persisted: list[str] = []
    embedded: list[dict] = []

    if isinstance(schema.get("tables"), list):            # relational — no embedding
        persisted = [t.get("name") for t in schema["tables"] if t.get("name")]
    elif isinstance(schema.get("collections"), list):     # document — find subdocuments
        for c in schema["collections"]:
            root = c.get("model") or c.get("name")
            if root:
                persisted.append(root)

            def walk(fields, owner):
                for f in fields or []:
                    if f.get("fields"):                   # nested object => embedded
                        embedded.append({"name": f.get("name"), "embedded_in": owner})
                        walk(f["fields"], owner)          # deeper nesting still owned by root
            walk(c.get("fields"), root)
    elif isinstance(schema.get("entities"), list):        # native
        persisted = list(schema["entities"])

    return {"persisted_stores": persisted, "embedded_entities": embedded}


def distill(inputs: dict) -> dict:
    """Only what's needed to shape a backend layout, to keep the prompt focused."""
    er = inputs["extracted_requirements"] or {}
    uf = inputs["user_features"] or {}
    schema = inputs["db_schema"] or {}
    # Authoritative data shape from the schema: which entities are their own
    # store vs. embedded in a parent. This is what keeps the backend from
    # modelling an embedded entity (e.g. a menu embedded in a restaurant) as a
    # separate collection/table the schema never created.
    dm = _extract_data_model(schema)
    return {
        "tech_stack": er.get("tech_stack", []),
        "constraints": er.get("constraints", []),
        "external_interfaces": er.get("external_interfaces", []),
        "non_functional": er.get("non_functional", []),
        "features": [{"name": f.get("name"), "description": f.get("description")}
                     for f in uf.get("features", [])],
        "roles": [r.get("role") for r in uf.get("roles", [])],
        "datastore": schema.get("datastore"),
        "datastore_product": schema.get("datastore_product"),
        # persisted_stores == the data objects that get their own model/repository
        "data_objects": dm["persisted_stores"],
        "persisted_stores": dm["persisted_stores"],
        "embedded_entities": dm["embedded_entities"],
        # Frontend alignment (empty when routes.json isn't present yet)
        "frontend_routes": _extract_routes(inputs.get("routes")),
    }



# ---------------------------------------------------------------------------
# LLM plumbing (Azure AI Foundry; patchable for tests)
# ---------------------------------------------------------------------------
def _client():
    try:
        from anthropic import AnthropicFoundry
    except ImportError:
        raise SystemExit("The 'anthropic' package is required. pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is empty. Set it in .env to your Azure Foundry key.")
    if not ANTHROPIC_ENDPOINT:
        raise SystemExit("ANTHROPIC_ENDPOINT is empty. Set it to your Foundry base URL "
                         "(…/anthropic).")
    return AnthropicFoundry(api_key=api_key, base_url=ANTHROPIC_ENDPOINT, timeout=180.0)


def _call_json(system: str, user: str, max_tokens: int = MAX_TOKENS) -> dict:
    resp = _client().messages.create(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1:
            return json.loads(text[s:e + 1])
        raise


# ---------------------------------------------------------------------------
# Prompts (domain-neutral; stack-aware from the inputs)
# ---------------------------------------------------------------------------
DELIBERATE_SYSTEM = """You are a senior backend architect. Given an application's \
tech stack, features, non-functional needs and data model, reason about how best \
to organise its backend source tree.

Propose 2-3 GENUINELY DIFFERENT structural approaches (not trivial variants) that \
suit the app's actual stack and framework. Consider axes such as: layering by \
technical role (controllers / services / repositories / entities) vs. feature or \
domain modules (a folder per feature owning its own routes, service and data \
access) vs. a hybrid; where cross-cutting concerns (config, middleware, auth, \
validation, errors) live; and how the data-access layer is shaped for the chosen \
datastore. For each approach give concrete pros and cons FOR THIS APP and stack. \
Then pick the best and justify it briefly.

Respond with STRICT JSON only, no prose, no markdown fences:
{
  "approaches": [
    {"name": "...", "summary": "...", "pros": ["..."], "cons": ["..."]}
  ],
  "chosen": "<name of the chosen approach>",
  "rationale": "<why this is best for this app and stack>"
}"""

GENERATE_SYSTEM = """You are a senior backend architect implementing the chosen \
structure. Produce the concrete backend project tree for the app's ACTUAL stack \
and datastore.

Rules:
- Reflect the real framework conventions of the stack in the inputs (e.g. an \
Express/Node layout differs from NestJS, Django, Spring, or FastAPI). Name the \
entry file and directories the way that stack actually does.
- Shape the data-access layer for the datastore: ORM entities + migrations for a \
relational store; ODM models (e.g. Mongoose schemas) with no SQL migrations for a \
document store; native client wrappers otherwise.
- RESPECT THE SCHEMA'S DATA SHAPE. `persisted_stores` are the ONLY entities that \
get their own data model / repository (their own table or collection). \
`embedded_entities` are stored INSIDE a parent aggregate (subdocuments/nested \
records) — each lists the parent it is `embedded_in`. Do NOT give an embedded \
entity its own model, collection, table, migration, or repository: its data is \
read and written THROUGH the parent store's model and repository. You MAY still \
create a feature module (routes, controller, service) for behaviour around an \
embedded entity when the features call for it, but that module's data access must \
go through the owning aggregate — it must not declare a separate store. The schema \
is the source of truth for where each entity's data physically lives; never \
contradict it.
- Include folders for the features/modules implied by the inputs, plus the \
cross-cutting concerns the app needs (config, middleware, auth, validation, error \
handling, tests) — only those that make sense for this app.
- If `frontend_routes` are present in the inputs, align the backend to them: the \
backend's feature modules and API surface should serve the data those routes need. \
Treat them as alignment hints, not literal folders to copy — do NOT create backend \
folders named after individual UI pages. If they are empty/absent, ignore them and \
shape the backend from the features and data model alone.
- Do NOT invent product features beyond those implied by the inputs.

Output the layout as a NESTED JSON TREE under "tree": a directory maps to an \
OBJECT of its children; a leaf (file or an empty/utility directory) maps to a \
SHORT purpose STRING. Directory keys end with "/". Example shape (illustrative, \
adapt to the real stack):
{
  "tree": {
    "src/": {
      "modules/": "feature modules",
      "controllers/": "route handlers",
      "services/": "business logic",
      "entities/": "DB entities",
      "dto/": "request/response shapes",
      "migrations/": "DB migrations"
    },
    "package.json": "dependencies and scripts"
  },
  "notes": ["assumptions or things the human should confirm"]
}

Respond with STRICT JSON only, no prose, no markdown fences."""


# ---------------------------------------------------------------------------
# Reasoning steps
# ---------------------------------------------------------------------------
def deliberate(facts: dict) -> dict:
    user = ("Application facts:\n```json\n"
            + json.dumps(facts, indent=2, ensure_ascii=False)
            + "\n```\nPropose backend-structure approaches, compare, and choose one.")
    return _call_json(DELIBERATE_SYSTEM, user, max_tokens=2500)


def design(facts: dict, decision: dict) -> dict:
    user = ("Application facts:\n```json\n"
            + json.dumps(facts, indent=2, ensure_ascii=False)
            + "\n```\n\nChosen approach:\n```json\n"
            + json.dumps({"chosen": decision.get("chosen"),
                          "rationale": decision.get("rationale")}, indent=2, ensure_ascii=False)
            + "\n```\nProduce the backend folder tree for the chosen approach.")
    return _call_json(GENERATE_SYSTEM, user, max_tokens=MAX_TOKENS)


def generate_structure(inputs: dict) -> dict:
    facts = distill(inputs)
    logger.info("Deliberating on backend-structure approaches (model=%s)...", MODEL)
    decision = deliberate(facts)
    logger.info("Chosen approach: %s", decision.get("chosen"))
    logger.info("Generating backend folder tree...")
    result = design(facts, decision)
    tree = result.get("tree", result)          # tolerate a bare tree
    structure = {"tree": tree, "notes": result.get("notes", [])}
    logger.info("Backend structure generated: %d top-level entries",
                len(tree) if isinstance(tree, dict) else 0)
    return {"decision": decision, "structure": structure, "facts": facts}


# ---------------------------------------------------------------------------
# Light deterministic self-validation (warnings only)
# ---------------------------------------------------------------------------
def validate_structure(structure: dict, facts: dict) -> list[str]:
    warnings: list[str] = []
    tree = structure.get("tree")
    if not isinstance(tree, dict) or not tree:
        warnings.append("backend tree is empty or not an object")
        return warnings

    # collect all keys anywhere in the tree
    keys: list[str] = []
    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                keys.append(k.lower())
                walk(v)
    walk(tree)
    blob = " ".join(keys)

    # datastore-appropriate data layer present?
    ds = (facts.get("datastore") or "").lower()
    if ds == "relational":
        if "migrat" not in blob:
            warnings.append("relational datastore but no migrations folder in the tree")
        if not any(w in blob for w in ("entit", "model", "repositor")):
            warnings.append("no entities/models/repositories folder for the data layer")
    elif ds == "document":
        if not any(w in blob for w in ("model", "schema", "entit")):
            warnings.append("document datastore but no models/schemas folder in the tree")

    # a couple of near-universal concerns worth confirming
    for concern in ("config", "route"):
        if concern not in blob and concern[:-1] not in blob:
            warnings.append(f"no obvious '{concern}' location in the tree")

    # Embedded entities must NOT be given their own data store. Flag any
    # model/schema/entity/repository/migration/collection file whose name matches
    # an embedded entity — this is the schema-vs-backend "where does the data live"
    # contradiction (e.g. a menu embedded in a restaurant handed its own model).
    # Heuristic and warning-only, consistent with the rest of this validator.
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z]", "", str(s).lower())

    def _stem(s: str) -> str:
        n = _norm(s)
        if n.endswith("ies") and len(n) > 6:
            return n[:-3] + "y"
        for suf in ("es", "s"):
            if n.endswith(suf) and len(n) - len(suf) >= 3:
                return n[:-len(suf)]
        return n

    store_re = re.compile(r"(model|schema|entity|entities|repositor|migration|collection)")
    # A store file whose name matches a PERSISTED store is legitimate (it's that
    # store's own model/repository) — exclude it so an embedded field that merely
    # shares a prefix with a real store (e.g. deliveryAddress vs. the Delivery
    # collection) doesn't produce a false positive.
    persisted_stems = {_stem(p) for p in (facts.get("persisted_stores") or [])}
    store_keys = [k for k in keys
                  if store_re.search(k) and _stem(k.split(".")[0]) not in persisted_stems]
    for emb in (facts.get("embedded_entities") or []):
        name = emb.get("name") if isinstance(emb, dict) else emb
        parent = emb.get("embedded_in") if isinstance(emb, dict) else None
        est = _stem(name or "")
        if len(est) < 4:                       # too short/generic to match safely
            continue
        for k in store_keys:
            ks = _stem(k.split(".")[0])         # file stem before the first dot
            if len(ks) < 4:
                continue
            if ks == est or ks.startswith(est) or est.startswith(ks):
                where = f" (embedded in {parent})" if parent else ""
                warnings.append(
                    f"'{k}' looks like a dedicated data store for embedded entity "
                    f"'{name}'{where}; per the schema this data lives inside its parent "
                    f"and should be accessed through it, not persisted separately")
                break
    return warnings


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def _tree_lines(node, prefix="") -> list[str]:
    lines = []
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict):
                lines.append(f"{prefix}{k}")
                lines += _tree_lines(v, prefix + "  ")
            else:
                lines.append(f"{prefix}{k}  — {v}")
    return lines


def render_decision_md(decision: dict, structure: dict) -> str:
    lines = ["# Backend Structure — Design Decision\n"]
    for a in decision.get("approaches", []):
        lines.append(f"## {a.get('name', '(unnamed approach)')}")
        if a.get("summary"):
            lines.append(a["summary"])
        if a.get("pros"):
            lines.append("\n**Pros**")
            lines += [f"- {p}" for p in a["pros"]]
        if a.get("cons"):
            lines.append("\n**Cons**")
            lines += [f"- {c}" for c in a["cons"]]
        lines.append("")
    lines.append(f"## Chosen: {decision.get('chosen', '(none)')}")
    lines.append(decision.get("rationale", ""))
    lines.append("\n## Resulting layout")
    lines += ["```"] + _tree_lines(structure.get("tree", {})) + ["```"]
    if structure.get("notes"):
        lines.append("\n## Notes")
        lines += [f"- {n}" for n in structure["notes"]]
    return "\n".join(lines)


def write_outputs(shared: Path, result: dict) -> dict:
    paths = {"json": shared / OUT_JSON, "decision": shared / OUT_DECISION}
    paths["json"].write_text(
        json.dumps(result["structure"], indent=2, ensure_ascii=False), encoding="utf-8")
    paths["decision"].write_text(
        render_decision_md(result["decision"], result["structure"]), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}


# ---------------------------------------------------------------------------
# Reusable core + entrypoints
# ---------------------------------------------------------------------------
def run(shared_dir: str | None = None, inputs: dict | None = None) -> dict:
    load_dotenv_files()
    shared = resolve_shared_dir(shared_dir)
    if inputs is None:
        inputs = load_inputs(shared)
    result = generate_structure(inputs)
    result["warnings"] = validate_structure(result["structure"], result["facts"])
    result["paths"] = write_outputs(shared, result)
    return result


def backend_structure_node(state: dict) -> dict:
    """LangGraph node. Reads `shared_dir` (and optional preloaded `inputs`) from
    state; returns the backend structure to merge back into state."""
    shared_dir = state.get("shared_dir") or state.get("SHARED_DIR")
    inputs = state.get("inputs")
    result = run(shared_dir=shared_dir, inputs=inputs)
    return {
        "backend_structure": result["structure"],
        "backend_structure_decision": result["decision"],
        "backend_structure_paths": result["paths"],
        "backend_structure_warnings": result["warnings"],
    }


def main():
    ap = argparse.ArgumentParser(description="Generate the backend structure from the Level-1/2 artifacts")
    ap.add_argument("--dir", default=None, help=f"shared folder (inputs in, outputs out). Overrides ${ENV_VAR}.")
    args = ap.parse_args()

    result = run(shared_dir=args.dir)
    print(f"Chosen approach: {result['decision'].get('chosen')}")
    print(f"backend-structure.json -> {result['paths']['json']}")
    for w in result["warnings"]:
        print(f"  ⚠ {w}")


if __name__ == "__main__":
    main()