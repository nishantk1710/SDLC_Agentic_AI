#!/usr/bin/env python3
"""
schema_generator.py  —  Level-2 Schema Generator agent

Consumes the Level-1 artifacts (extracted_requirements.json, user_features.json,
glossary.json) from the shared folder and produces a relational DB schema.

Reasoning style (as requested):
    1. DELIBERATE — the model studies the entities, requirements and business
       rules and proposes 2-3 genuinely different modelling approaches, each
       with concrete pros/cons for THIS app.
    2. DECIDE     — it compares them and picks the best, with a rationale.
    3. GENERATE   — it produces the concrete schema for the chosen approach as
       structured JSON.
The agent then renders well-formed DDL *deterministically* from that JSON, so
the SQL is always valid and downstream agents get a machine-readable schema.

Outputs (written to the shared folder):
    db_schema.json       structured schema (tables/columns/fks/indexes)
    db_schema.sql        deterministically rendered PostgreSQL DDL
    db_schema_decision.md the approaches considered + chosen + rationale

Two entrypoints, one core:
    • CLI:        python schema_generator.py            (uses $SHARED_DIR)
    • LangGraph:  from schema_generator import schema_generator_node
                  graph.add_node("schema", schema_generator_node)

Environment:
    SHARED_DIR          folder holding the Level-1 artifacts + where outputs go
    ANTHROPIC_API_KEY   key for the LLM calls
    SCHEMA_MODEL        model id (default 'claude-sonnet-4-5'; set to whatever
                        your account supports)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Any


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("schema_generator")


def load_dotenv_files() -> None:
    """Load .env if python-dotenv is installed (optional). Real env vars win.
    Called at import time (below) so EVERY os.environ.get() in this module —
    and the Anthropic SDK's own ANTHROPIC_API_KEY lookup — sees the .env values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env", override=False)   # .env next to this script
    load_dotenv(override=False)                  # .env in the current dir, if any


# Load .env BEFORE reading any configuration below.
load_dotenv_files()

# ---------------------------------------------------------------------------
# Config — read from the environment (populated from .env just above)
# ---------------------------------------------------------------------------
ENV_VAR = "SHARED_DIR"
# Model is configurable. On Azure Foundry this is your DEPLOYMENT NAME.
MODEL = os.environ.get("DEFAULT_MODEL") or "claude-sonnet-5"
# Optional hard override of the datastore choice: "relational"/"postgresql"/"mysql"
# or "mongodb"/"mongo". When unset, the datastore is detected from the SRS tech stack.
DATASTORE_OVERRIDE = (os.environ.get("SCHEMA_DATASTORE") or "").strip().lower()
DIALECT = os.environ.get("SCHEMA_DIALECT", "postgresql")
# Foundry base URL, e.g. https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_ENDPOINT = os.environ.get("ANTHROPIC_ENDPOINT") or None
# int() on an empty string throws, so fall back when the env value is blank.
MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS") or "8000")

IN_REQUIREMENTS = "extracted_requirements.json"
IN_FEATURES = "user_features.json"
IN_GLOSSARY = "glossary.json"

OUT_JSON = "db_schema.json"
OUT_SQL = "db_schema.sql"                 # relational output
OUT_MODELS = "db_models.js"               # MongoDB / Mongoose output
OUT_DECISION = "db_schema_decision.md"


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------
def resolve_shared_dir(cli_dir: str | None) -> Path:
    raw = cli_dir or os.environ.get(ENV_VAR)
    if not raw:
        raise SystemExit(
            f"No location set. Set {ENV_VAR} (the folder with the Level-1 artifacts) "
            f"or pass --dir."
        )
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise SystemExit(f"{ENV_VAR} is not a directory: {p}")
    return p


def load_inputs(shared: Path) -> dict:
    """Read the three Level-1 artifacts. Fails clearly if any is missing."""
    def read(name: str) -> dict:
        f = shared / name
        if not f.is_file():
            raise SystemExit(f"Missing Level-1 input: {f}. Run the SRS parser first.")
        return json.loads(f.read_text(encoding="utf-8"))

    return {
        "extracted_requirements": read(IN_REQUIREMENTS),
        "user_features": read(IN_FEATURES),
        "glossary": read(IN_GLOSSARY),
    }


def distill(inputs: dict) -> dict:
    """Pull just the schema-relevant facts, to keep the prompt focused."""
    er = inputs["extracted_requirements"]
    uf = inputs["user_features"]
    return {
        "entities": uf.get("entities", []),
        "roles": [r.get("role") for r in uf.get("roles", [])],
        "features": [{"name": f.get("name"), "description": f.get("description")}
                     for f in uf.get("features", [])],
        "functional_requirements": er.get("functional", []),
        "business_rules": er.get("business_rules", []),
        "constraints": er.get("constraints", []),
        "tech_stack": er.get("tech_stack", []),
        "glossary": inputs["glossary"].get("terms", []),
    }


def _tech_text(inputs: dict) -> str:
    """All datastore-relevant text from the SRS, lower-cased, for detection."""
    er = inputs["extracted_requirements"]
    parts: list[str] = []
    ts = er.get("tech_stack")
    if isinstance(ts, list):
        parts += [str(item.get("text", "")) for item in ts]
    elif isinstance(ts, str):
        parts.append(ts)
    parts += [str(c) for c in er.get("constraints", [])]
    parts += [f"{e.get('name','')} {e.get('description','')}"
              for e in er.get("external_interfaces", [])]
    return " ".join(parts).lower()


def _relational_dialect(text: str) -> str:
    for key, dia in (("postgres", "postgresql"), ("cockroach", "postgresql"),
                     ("mysql", "mysql"), ("mariadb", "mysql"),
                     ("sqlite", "sqlite"), ("sql server", "sqlserver"),
                     ("sqlserver", "sqlserver"), ("oracle", "oracle")):
        if key in text:
            return dia
    return DIALECT


# Datastores we recognise when an SRS *declares* one. The value describes how to
# render it. Anything not listed can still be CHOSEN by the model (see below) and
# is emitted as a native artifact rather than via a built-in renderer.
_DECLARED_SIGNALS = [
    # (keywords, kind, render, display, extra)
    (("mongodb", "mongoose", "mern", "documentdb"), "document", "mongoose", "MongoDB", {"odm": "Mongoose"}),
    (("postgres", "postgresql", "cockroach", "mysql", "mariadb", "sqlite",
      "sql server", "sqlserver", "oracle", "relational database", "rdbms"),
     "relational", "sql", "SQL", {}),
    (("dynamodb",), "wide_column", "native", "DynamoDB", {}),
    (("cassandra", "scylla"), "wide_column", "native", "Cassandra", {}),
    (("neo4j", "graph database", "gremlin"), "graph", "native", "Neo4j", {}),
    (("elasticsearch", "opensearch"), "search", "native", "Elasticsearch", {}),
    (("redis",), "key_value", "native", "Redis", {}),
    (("firestore", "firebase"), "document", "native", "Firestore", {}),
    (("prisma",), "relational", "sql", "SQL (via Prisma)", {}),
]


def resolve_datastore(inputs: dict) -> dict:
    """Decide the target datastore. Priority:
    1. SCHEMA_DATASTORE env override.
    2. A datastore the SRS explicitly declares (tech stack / constraints).
    3. Otherwise 'undeclared' — the model chooses the best fit during deliberation.
    """
    ov = (os.environ.get("SCHEMA_DATASTORE") or "").strip().lower()
    if ov:
        if ov in ("mongodb", "mongo", "document"):
            return {"kind": "document", "render": "mongoose", "name": "MongoDB", "odm": "Mongoose"}
        if ov in ("relational", "sql", "postgresql", "postgres", "mysql", "mariadb", "sqlite", "oracle", "sqlserver"):
            d = "postgresql" if ov in ("relational", "sql", "postgres", "postgresql") else ov
            return {"kind": "relational", "render": "sql", "name": d, "dialect": d}
        # any other explicit override -> treat as a named store rendered natively
        return {"kind": "other", "render": "native", "name": DATASTORE_OVERRIDE}

    text = _tech_text(inputs)
    for keys, kind, render, display, extra in _DECLARED_SIGNALS:
        if any(k in text for k in keys):
            target = {"kind": kind, "render": render, "name": display, **extra}
            if kind == "relational":
                target["dialect"] = _relational_dialect(text)
                target["name"] = target["dialect"]
            return target

    # Nothing declared: let the model pick from the full landscape.
    return {"kind": "undeclared", "render": None, "name": "(model chooses)"}


# Backwards-compatible alias
detect_datastore = resolve_datastore


# ---------------------------------------------------------------------------
# LLM plumbing (patchable for testing)
# ---------------------------------------------------------------------------
def _client():
    """Build an Azure AI Foundry client, matching the frontend agent's pattern."""
    try:
        from anthropic import AnthropicFoundry
    except ImportError:
        raise SystemExit("The 'anthropic' package is required. pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is empty. Set it in .env to your Azure Foundry key "
            "(the 'Key' value from your Claude deployment's Details tab)."
        )
    if not ANTHROPIC_ENDPOINT:
        raise SystemExit(
            "ANTHROPIC_ENDPOINT is empty. Set it to your Foundry base URL, e.g. "
            "https://<resource>.services.ai.azure.com/anthropic"
        )
    return AnthropicFoundry(api_key=api_key, base_url=ANTHROPIC_ENDPOINT, timeout=180.0)


def _call_json(system: str, user: str, max_tokens: int = MAX_TOKENS) -> dict:
    """Call the model and parse a JSON object from the reply."""
    resp = _client().messages.create(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    """Robustly extract a JSON object from a model reply."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
_SELECT_CLAUSE = (
    "This application has NOT fixed a datastore. FIRST choose the most appropriate one, "
    "considering the FULL landscape — relational (e.g. PostgreSQL, MySQL), document "
    "(e.g. MongoDB), key-value (e.g. Redis), wide-column (e.g. Cassandra, DynamoDB), "
    "graph (e.g. Neo4j), search (e.g. Elasticsearch), or time-series — judging by the "
    "data's shape, relationship density, primary access patterns, consistency needs and "
    "expected scale. Name the chosen family and a concrete product. THEN propose "
    "approaches to model the data within it.")
_WITHIN_CLAUSE = ("The target datastore is {store} (already fixed by the project). "
    "Propose approaches to model the data within it.")

DELIBERATE_SYSTEM = """You are a senior data architect. Study the entities, features, \
functional requirements and business rules of an application and reason carefully \
about how to model its data.

{lead}

Propose 2-3 GENUINELY DIFFERENT modelling approaches (not trivial variants), each \
appropriate to the datastore. Consider axes such as: {axes} For each approach give \
concrete pros and cons FOR THIS APP specifically. Then pick the best and justify it.

Respond with STRICT JSON only, no prose, no markdown fences:
{{
  "datastore": {{"family": "<relational|document|key_value|wide_column|graph|search|time_series>", "product": "<concrete product>", "why": "<why it fits; empty string if it was already fixed>"}},
  "approaches": [
    {{"name": "...", "summary": "...", "pros": ["..."], "cons": ["..."]}}
  ],
  "chosen": "<name of the chosen approach>",
  "rationale": "<why this approach is best for this app>"
}}"""

_AXES_RELATIONAL = ("normalisation vs. denormalisation; how subtype/role entities are "
    "modelled (single table + type column vs. table-per-type vs. shared-PK); how "
    "many-to-many and reference/lookup data are handled; how status/lifecycle, money "
    "and time are typed.")
_AXES_DOCUMENT = ("what to EMBED vs. REFERENCE; where document boundaries fall relative "
    "to the main read/write patterns; how subtype entities are modelled; where to "
    "denormalise for reads; and the risk of unbounded, ever-growing arrays.")
_AXES_GENERIC = ("how the primary access patterns map to keys/partitions/indexes; how "
    "relationships are expressed in this datastore's idioms; and consistency vs. "
    "denormalisation tradeoffs.")

def _axes_for(family: str) -> str:
    return {"relational": _AXES_RELATIONAL, "document": _AXES_DOCUMENT}.get(family, _AXES_GENERIC)

GENERATE_RELATIONAL_SYSTEM = """You are a senior database architect implementing the \
chosen design for a relational database. Produce the concrete schema.

Rules:
- Dialect: {dialect}. snake_case names; table names plural.
- Give every table a primary key (prefer a surrogate id using the dialect's idiomatic \
UUID/identity type and default).
- Add created_at/updated_at timestamps where they make sense, with sensible defaults.
- Resolve many-to-many relationships with explicit join tables.
- Map every domain entity to a table; do NOT invent entities beyond those implied.
- Encode business rules as CHECK / UNIQUE constraints wherever expressible in DDL.
- Add foreign keys with a sensible ON DELETE, and indexes on foreign keys and on \
columns used for common lookups/filters.

Respond with STRICT JSON only, no prose, no markdown fences:
{{
  "datastore": "relational",
  "dialect": "{dialect}",
  "tables": [
    {{
      "name": "<table>",
      "comment": "one line on what it holds",
      "columns": [
        {{"name": "id", "type": "<uuid/identity type>", "nullable": false, "default": "<default>", "constraints": []}}
      ],
      "primary_key": ["id"],
      "unique": [["<col>"]],
      "checks": ["<boolean expression>"],
      "foreign_keys": [
        {{"columns": ["<fk_col>"], "ref_table": "<other_table>", "ref_columns": ["id"], "on_delete": "CASCADE"}}
      ],
      "indexes": [{{"name": "<idx_name>", "columns": ["<col>"], "unique": false}}]
    }}
  ],
  "notes": ["assumptions or things the human should confirm"]
}}"""

GENERATE_MONGO_SYSTEM = """You are a senior data architect implementing the chosen \
document-model design for MongoDB with Mongoose. Produce the concrete schema.

Rules:
- One collection per aggregate root; camelCase field names; collection names plural.
- Deliberately EMBED tightly-owned, read-together data as subdocuments; REFERENCE \
independent entities by ObjectId with a `ref` to the target collection. Justify the \
significant embed/reference choices in "notes".
- Map every domain entity to a collection or an embedded subdocument; do NOT invent \
entities beyond those implied.
- Field types: String, Number, Boolean, Date, ObjectId, Mixed, Buffer, Decimal128. \
For arrays use "[Type]" (e.g. "[String]"). For an embedded subdocument use type \
"Object" (or "[Object]" for a list) and nest its "fields". For a reference set type \
"ObjectId" and add "ref": "<ModelName>".
- Mark required/unique fields; use enums for fixed value sets; choose money/precision \
types deliberately.
- created_at/updated_at are handled by Mongoose timestamps — do NOT add them manually.
- Add indexes for common lookups and uniqueness constraints. An index entry may set:
  "unique"/"sparse" (booleans), "expireAfterSeconds" (TTL), a "type" for the whole
  index ("2dsphere" for GeoJSON location fields, "text", "hashed"), and either a list
  of field paths OR an object mapping each path to 1/-1/"2dsphere"/"text" for full
  control. GeoJSON point fields ({type:"Point", coordinates:[lng,lat]}) MUST get a
  "2dsphere" index to support geo queries; ephemeral collections can use a TTL index.

Respond with STRICT JSON only, no prose, no markdown fences:
{{
  "datastore": "document",
  "odm": "mongoose",
  "collections": [
    {{
      "name": "<plural_name>",
      "model": "<ModelName>",
      "comment": "one line on what it holds",
      "fields": [
        {{"name": "<field>", "type": "String", "required": true, "unique": false}},
        {{"name": "<statusField>", "type": "String", "enum": ["<a>", "<b>"]}},
        {{"name": "<refField>", "type": "ObjectId", "ref": "<OtherModel>"}},
        {{"name": "<embedded>", "type": "[Object]", "fields": [
            {{"name": "<subfield>", "type": "String", "required": true}}
        ]}}
      ],
      "indexes": [{{"fields": ["<field>"], "unique": true}}]
    }}
  ],
  "notes": ["assumptions, and key embed-vs-reference decisions the human should confirm"]
}}"""

GENERATE_NATIVE_SYSTEM = """You are a senior data architect implementing the chosen \
design for {product} (a {family} datastore). Produce the schema in that datastore's \
OWN idiomatic form.

Rules:
- Use the native modelling concepts and definition language of {product} (e.g. \
keyspaces/tables with partition & clustering keys for Cassandra; table + key schema + \
GSIs for DynamoDB; node/relationship definitions and constraints for a graph DB; \
index mappings for a search engine).
- Design around the application's primary access patterns.
- Map every domain entity; do NOT invent entities beyond those implied.

Respond with STRICT JSON only, no prose, no markdown fences:
{{
  "datastore": "{family}",
  "product": "{product}",
  "entities": ["<name>", "..."],
  "artifact_ext": "<extension for the native artifact, e.g. cql, cypher, json, txt>",
  "native_artifact": "<the COMPLETE idiomatic schema/DDL as a single string>",
  "notes": ["assumptions or things the human should confirm"]
}}"""


# ---------------------------------------------------------------------------
# The two reasoning steps
# ---------------------------------------------------------------------------
def deliberate(facts: dict, target: dict) -> dict:
    undeclared = target["kind"] == "undeclared"
    lead = _SELECT_CLAUSE if undeclared else _WITHIN_CLAUSE.format(store=target["name"])
    family = "" if undeclared else ("document" if target.get("render") == "mongoose"
                                    else target["kind"])
    system = DELIBERATE_SYSTEM.format(lead=lead, axes=_axes_for(family))
    user = ("Application facts:\n```json\n"
            + json.dumps(facts, indent=2, ensure_ascii=False)
            + "\n```\n"
            + ("Choose the datastore, then propose approaches, compare, and choose one."
               if undeclared else "Propose approaches, compare, and choose one."))
    return _call_json(system, user, max_tokens=2500)


def _target_from_family(family: str, product: str) -> dict:
    """Map a model-chosen {family, product} to a concrete render target."""
    fam, prod = (family or "").lower(), (product or "").lower()
    if fam == "relational" or any(p in prod for p in
            ("postgres", "mysql", "maria", "sqlite", "oracle", "sql server", "cockroach")):
        dia = _relational_dialect(prod) if prod else DIALECT
        return {"kind": "relational", "render": "sql", "name": dia, "dialect": dia}
    if fam == "document":
        if "mongo" in prod or not prod:
            return {"kind": "document", "render": "mongoose",
                    "name": product or "MongoDB", "odm": "Mongoose"}
        return {"kind": "document", "render": "native", "name": product}
    return {"kind": fam or "other", "render": "native", "name": product or (family or "datastore")}


def design(facts: dict, decision: dict, target: dict) -> dict:
    render = target["render"]
    if render == "sql":
        system = GENERATE_RELATIONAL_SYSTEM.format(dialect=target.get("dialect", DIALECT))
    elif render == "mongoose":
        system = GENERATE_MONGO_SYSTEM
    else:
        system = GENERATE_NATIVE_SYSTEM.format(product=target.get("name", "the datastore"),
                                               family=target.get("kind", "other"))
    user = (
        "Application facts:\n```json\n"
        + json.dumps(facts, indent=2, ensure_ascii=False)
        + "\n```\n\nChosen approach:\n```json\n"
        + json.dumps({"chosen": decision.get("chosen"),
                      "rationale": decision.get("rationale")}, indent=2, ensure_ascii=False)
        + "\n```\nProduce the schema for the chosen approach."
    )
    return _call_json(system, user, max_tokens=MAX_TOKENS)


def generate_schema(inputs: dict) -> dict:
    """Core: resolve/choose datastore -> deliberate -> decide -> generate."""
    facts = distill(inputs)
    target = resolve_datastore(inputs)
    if target["kind"] == "undeclared":
        logger.info("No datastore declared in the SRS — the model will choose one.")
    else:
        logger.info("Datastore from SRS: %s (%s)", target["name"], target["kind"])

    logger.info("Deliberating (model=%s)...", MODEL)
    decision = deliberate(facts, target)

    # If the datastore was undeclared, adopt the model's choice.
    if target["kind"] == "undeclared":
        ds = decision.get("datastore") or {}
        target = _target_from_family(ds.get("family", ""), ds.get("product", ""))
        logger.info("Model chose datastore: %s (%s)", target["name"], target["kind"])

    logger.info("Chosen approach: %s", decision.get("chosen"))
    logger.info("Generating concrete schema for %s...", target["name"])
    schema = design(facts, decision, target)
    schema.setdefault("datastore", target["kind"])
    schema["datastore_product"] = target["name"]
    if target["render"] == "sql":
        schema.setdefault("dialect", target.get("dialect", DIALECT))
        logger.info("Schema generated: %d tables", len(schema.get("tables", [])))
    elif target["render"] == "mongoose":
        logger.info("Schema generated: %d collections", len(schema.get("collections", [])))
    else:
        logger.info("Schema generated: native %s artifact", target["name"])
    return {"decision": decision, "schema": schema, "target": target}


# ---------------------------------------------------------------------------
# Deterministic DDL rendering (no LLM) — keeps the SQL always valid
# ---------------------------------------------------------------------------
def render_sql(schema: dict) -> str:
    dialect = schema.get("dialect", DIALECT)
    out: list[str] = ["-- Generated by schema_generator", f"-- dialect: {dialect}", ""]
    if str(dialect).startswith("postgres"):
        out += ['CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()', ""]

    fks: list[str] = []
    idxs: list[str] = []
    for t in schema.get("tables", []):
        name = t["name"]
        cols: list[str] = []
        for c in t.get("columns", []):
            parts = [c["name"], c.get("type", "TEXT")]
            if c.get("nullable") is False:
                parts.append("NOT NULL")
            if c.get("default") not in (None, ""):
                parts.append(f'DEFAULT {c["default"]}')
            parts += list(c.get("constraints", []))
            cols.append("    " + " ".join(str(p) for p in parts))
        if t.get("primary_key"):
            cols.append(f'    PRIMARY KEY ({", ".join(t["primary_key"])})')
        for u in t.get("unique", []):
            u = u if isinstance(u, list) else [u]
            cols.append(f'    UNIQUE ({", ".join(u)})')
        for chk in t.get("checks", []):
            cols.append(f"    CHECK ({chk})")
        out.append(f"CREATE TABLE {name} (\n" + ",\n".join(cols) + "\n);")
        out.append("")

        for fk in t.get("foreign_keys", []):
            fcols = ", ".join(fk["columns"])
            rcols = ", ".join(fk.get("ref_columns", ["id"]))
            od = f' ON DELETE {fk["on_delete"]}' if fk.get("on_delete") else ""
            cname = f'fk_{name}_{"_".join(fk["columns"])}'
            fks.append(f"ALTER TABLE {name} ADD CONSTRAINT {cname} "
                       f"FOREIGN KEY ({fcols}) REFERENCES {fk['ref_table']} ({rcols}){od};")
        for idx in t.get("indexes", []):
            uq = "UNIQUE " if idx.get("unique") else ""
            iname = idx.get("name") or f'idx_{name}_{"_".join(idx["columns"])}'
            idxs.append(f'CREATE {uq}INDEX {iname} ON {name} ({", ".join(idx["columns"])});')

    if fks:
        out += ["-- Foreign keys", *fks, ""]
    if idxs:
        out += ["-- Indexes", *idxs, ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Deterministic Mongoose rendering (no LLM) — for MongoDB schemas
# ---------------------------------------------------------------------------
def _singularize(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("ses"):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def _model_name(coll: dict) -> str:
    if coll.get("model"):
        return coll["model"]
    base = _singularize(coll["name"])
    return "".join(p.capitalize() for p in re.split(r"[_\s]+", base))


_JS_TYPE = {
    "string": "String", "number": "Number", "boolean": "Boolean", "date": "Date",
    "objectid": "Schema.Types.ObjectId", "mixed": "Schema.Types.Mixed",
    "buffer": "Buffer", "decimal128": "Schema.Types.Decimal128",
}


def _render_field(f: dict, indent: int) -> str:
    pad = "  " * indent
    typ = str(f.get("type", "String")).strip()
    is_array = typ.startswith("[") and typ.endswith("]")
    inner = typ[1:-1].strip() if is_array else typ

    # embedded subdocument(s)
    if inner.lower() in ("object", "subdocument", "document") and f.get("fields"):
        body = ",\n".join(_render_field(sf, indent + 1) for sf in f["fields"])
        block = "{\n" + body + "\n" + pad + "}"
        return f"{pad}{f['name']}: " + (f"[{block}]" if is_array else block)

    # scalar / reference
    js = _JS_TYPE.get(inner.lower(), "Schema.Types.Mixed")
    opts = [f"type: {js}"]
    if f.get("ref"):
        opts[0] = "type: Schema.Types.ObjectId"
        opts.append(f"ref: '{f['ref']}'")
    if f.get("required"):
        opts.append("required: true")
    if f.get("unique"):
        opts.append("unique: true")
    if f.get("enum"):
        opts.append("enum: " + json.dumps(f["enum"]))
    if f.get("default") not in (None, ""):
        # json.dumps yields valid JS literals for str/bool/number/null
        # (true/false/0/"x"), unlike str() which emits Python's True/False.
        opts.append("default: " + json.dumps(f["default"]))
    spec = "{ " + ", ".join(opts) + " }"
    return f"{pad}{f['name']}: " + (f"[{spec}]" if is_array else spec)


def _idx_key(k: str) -> str:
    """Quote an index key if it isn't a bare JS identifier (dotted paths, etc.)."""
    return k if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", k) else f"'{k}'"


def _index_key_spec(idx: dict) -> str:
    """Render the index key object. Supports:
      - fields as a list  -> ascending, or the index `type` applied to each
        (e.g. a single 2dsphere/text/hashed field);
      - fields as an object {field: 1 | -1 | "2dsphere" | "text"} for full control.
    """
    fields = idx.get("fields", [])
    itype = idx.get("type")
    pairs: list[tuple[str, object]] = []
    if isinstance(fields, dict):
        pairs = list(fields.items())
    else:
        for k in fields:
            pairs.append((k, itype if itype else 1))
    parts = []
    for k, v in pairs:
        val = f"'{v}'" if isinstance(v, str) else str(v)
        parts.append(f"{_idx_key(k)}: {val}")
    return "{ " + ", ".join(parts) + " }"


def _index_options(idx: dict) -> str:
    """Render the index options object (unique/sparse/expireAfterSeconds/name)."""
    opts: list[str] = []
    if idx.get("unique"):
        opts.append("unique: true")
    if idx.get("sparse"):
        opts.append("sparse: true")
    if idx.get("expireAfterSeconds") is not None:
        opts.append(f"expireAfterSeconds: {int(idx['expireAfterSeconds'])}")
    if idx.get("name"):
        opts.append("name: " + json.dumps(idx["name"]))
    return (", { " + ", ".join(opts) + " }") if opts else ""


def render_mongoose(schema: dict) -> str:
    out = ["// Generated by schema_generator", "// datastore: mongodb (Mongoose)",
           "const mongoose = require('mongoose');", "const { Schema } = mongoose;", ""]
    models = []
    for coll in schema.get("collections", []):
        model = _model_name(coll)
        models.append(model)
        if coll.get("comment"):
            out.append(f"// {coll['comment']}")
        fields = ",\n".join(_render_field(f, 1) for f in coll.get("fields", []))
        out.append(f"const {model}Schema = new Schema({{\n{fields}\n}}, {{ timestamps: true }});")
        for idx in coll.get("indexes", []):
            out.append(f"{model}Schema.index({_index_key_spec(idx)}{_index_options(idx)});")
        out.append(f"const {model} = mongoose.model('{model}', {model}Schema);")
        out.append("")
    out.append("module.exports = { " + ", ".join(models) + " };")
    return "\n".join(out)


def render_decision_md(decision: dict) -> str:
    lines = ["# DB Schema — Design Decision\n"]
    for a in decision.get("approaches", []):
        lines.append(f"## {a.get('name','(unnamed approach)')}")
        if a.get("summary"):
            lines.append(a["summary"])
        if a.get("pros"):
            lines.append("\n**Pros**")
            lines += [f"- {p}" for p in a["pros"]]
        if a.get("cons"):
            lines.append("\n**Cons**")
            lines += [f"- {c}" for c in a["cons"]]
        lines.append("")
    lines.append(f"## Chosen: {decision.get('chosen','(none)')}")
    lines.append(decision.get("rationale", ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Light deterministic self-validation (warnings only)
# ---------------------------------------------------------------------------
def validate_schema(schema: dict, inputs: dict) -> list[str]:
    warnings: list[str] = []
    entities = inputs["user_features"].get("entities", [])

    def norm(s: str) -> str:
        return re.sub(r"[^a-z]", "", s.lower())

    def covered(e: str, name: str) -> bool:
        """Does normalized entity `e` plausibly map to normalized `name`?
        Handles simple + y->ies pluralization (delivery/deliveries, category/
        categories) so real collections aren't flagged as missing."""
        if e == name or e in name or name in e:
            return True
        if e + "s" == name or name + "s" == e:
            return True
        if e.rstrip("s") == name or name.rstrip("s") == e:
            return True
        if e.endswith("y") and e[:-1] + "ies" == name:
            return True
        if name.endswith("y") and name[:-1] + "ies" == e:
            return True
        return False

    if "collections" in schema:            # document / Mongoose
        colls = schema.get("collections", [])
        names = {c["name"] for c in colls}
        model_names = {_model_name(c) for c in colls}

        def ref_ok(ref: str) -> bool:
            r = norm(ref)
            return any(r == norm(m) or r == norm(n) or r + "s" == norm(n)
                       for m in model_names for n in names)

        def check_fields(coll_name: str, fields: list):
            for f in fields:
                if f.get("ref") and not ref_ok(f["ref"]):
                    warnings.append(f"collection '{coll_name}' field '{f.get('name')}' "
                                    f"references unknown model '{f['ref']}'")
                if f.get("fields"):
                    check_fields(coll_name, f["fields"])  # recurse into subdocuments

        for c in colls:
            check_fields(c["name"], c.get("fields", []))
        coll_norms = {norm(n) for n in names}
        for ent in entities:
            e = norm(ent)
            if not any(covered(e, cn) for cn in coll_norms):
                warnings.append(f"entity '{ent}' has no obvious collection")
        return warnings

    if "tables" not in schema:              # native (non-relational, non-Mongoose)
        if not str(schema.get("native_artifact", "")).strip():
            warnings.append("native schema artifact is empty")
        out_ents = [norm(e) for e in schema.get("entities", [])]
        for ent in entities:
            e = norm(ent)
            if out_ents and not any(e in o or o in e for o in out_ents):
                warnings.append(f"entity '{ent}' not obviously covered")
        return warnings

    # relational
    tables = schema.get("tables", [])
    names = {t["name"] for t in tables}
    for t in tables:
        has_pk = bool(t.get("primary_key")) or any(
            "PRIMARY KEY" in " ".join(str(x) for x in c.get("constraints", []))
            for c in t.get("columns", [])
        )
        if not has_pk:
            warnings.append(f"table '{t['name']}' has no primary key")
        for fk in t.get("foreign_keys", []):
            if fk["ref_table"] not in names:
                warnings.append(f"FK in '{t['name']}' references unknown table '{fk['ref_table']}'")
    table_norms = {norm(n) for n in names}
    for ent in entities:
        e = norm(ent)
        if not any(covered(e, tn) for tn in table_norms):
            warnings.append(f"entity '{ent}' has no obvious table")
    return warnings


# ---------------------------------------------------------------------------
# Writing outputs
# ---------------------------------------------------------------------------
def write_outputs(shared: Path, result: dict) -> dict:
    schema, decision, target = result["schema"], result["decision"], result["target"]
    paths = {
        "json": shared / OUT_JSON,
        "decision": shared / OUT_DECISION,
    }
    paths["json"].write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    paths["decision"].write_text(render_decision_md(decision), encoding="utf-8")
    render = target["render"]
    if render == "mongoose":
        paths["models"] = shared / OUT_MODELS
        paths["models"].write_text(render_mongoose(schema), encoding="utf-8")
    elif render == "sql":
        paths["sql"] = shared / OUT_SQL
        paths["sql"].write_text(render_sql(schema), encoding="utf-8")
    else:                                   # native artifact authored by the model
        ext = re.sub(r"[^a-z0-9]", "", str(schema.get("artifact_ext", "txt")).lower()) or "txt"
        artifact = shared / f"db_schema.{ext}"
        artifact.write_text(str(schema.get("native_artifact", "")), encoding="utf-8")
        paths["artifact"] = artifact
    return {k: str(v) for k, v in paths.items()}


# ---------------------------------------------------------------------------
# Reusable core used by BOTH entrypoints
# ---------------------------------------------------------------------------
def run(shared_dir: str | None = None, inputs: dict | None = None) -> dict:
    """Resolve dir -> load inputs -> deliberate/decide/generate -> write -> return."""
    load_dotenv_files()
    shared = resolve_shared_dir(shared_dir)
    if inputs is None:
        inputs = load_inputs(shared)
    result = generate_schema(inputs)
    result["warnings"] = validate_schema(result["schema"], inputs)
    result["paths"] = write_outputs(shared, result)
    return result


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------
def schema_generator_node(state: dict) -> dict:
    """LangGraph node. Reads `shared_dir` (and optional preloaded `inputs`) from
    state; returns schema artifacts to merge back into state.

    Example:
        from langgraph.graph import StateGraph
        graph = StateGraph(dict)
        graph.add_node("schema_generator", schema_generator_node)
        # state = {"shared_dir": "/path/to/shared"}
    """
    shared_dir = state.get("shared_dir") or state.get("SHARED_DIR")
    inputs = state.get("inputs")  # optional: pass artifacts directly to skip disk read
    result = run(shared_dir=shared_dir, inputs=inputs)
    return {
        "db_schema": result["schema"],
        "db_datastore": result["target"]["kind"],
        "db_schema_decision": result["decision"],
        "db_schema_paths": result["paths"],
        "db_schema_warnings": result["warnings"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Generate a DB schema from the Level-1 artifacts")
    ap.add_argument("--dir", default=None, help=f"shared folder (inputs in, outputs out). Overrides ${ENV_VAR}.")
    args = ap.parse_args()

    result = run(shared_dir=args.dir)
    schema, target = result["schema"], result["target"]
    print(f"Datastore: {target['name']} ({target['kind']})")
    print(f"Chosen approach: {result['decision'].get('chosen')}")
    if target["render"] == "mongoose":
        print(f"Collections: {len(schema.get('collections', []))} -> {result['paths'].get('models')}")
    elif target["render"] == "sql":
        print(f"Tables: {len(schema.get('tables', []))} -> {result['paths'].get('sql')}")
    else:
        print(f"Native {target['name']} schema -> {result['paths'].get('artifact')}")
    for w in result["warnings"]:
        print(f"  ⚠ {w}")


if __name__ == "__main__":
    main()