#!/usr/bin/env python3
"""
validation_rules_generator.py  —  Level-2 Validation Rules agent

Consumes the Level-1/Level-2 artifacts from the shared folder and produces the
per-field UI validation rules — the exact rule per field and the exact message
shown to the user — mirroring the DB constraints from §8.

Satisfies D4 (Validation Rules) of the design-to-implementation contract.

Inputs (read from the shared folder):
    extracted_requirements.json  domain/business rules (password reset, minimums, …)
    openapi.yaml                 request schemas — the input forms + required/type/format/enum
    sample-payloads.json         operationId -> {method, path, request, responses}
    db_schema.json               §8 datastore constraints (required/unique/enum/type) to mirror

Reasoning style (mirrors schema_generator.py / coding_guidelines_generator.py):
    1. DISTILL   — pull only the validation-relevant facts: every *Request schema
       (the forms users fill in), a flat index of DB field constraints, the
       endpoint each form posts to, example payloads, and the domain rules.
    2. GENERATE  — the model derives the exact validation rule per field and the
       exact human message, adding UI-only fields the API can't express (e.g. a
       `confirm` password field with `matches`), as structured JSON.
    3. NORMALISE — deterministically guarantee every rule has a message and that
       DB `unique`/`required`/`enum` constraints are reflected, so the artifact
       is always well-formed.

Output (written to the shared folder):
    validation-rules.json   forms -> field -> rule (each form matches the D4 shape)

Two entrypoints, one core:
    • CLI:        python validation_rules_generator.py       (uses $SHARED_DIR)
    • LangGraph:  from validation_rules_generator import validation_rules_node
                  graph.add_node("validation_rules", validation_rules_node)

Environment:
    SHARED_DIR          folder holding the artifacts + where the output goes
    ANTHROPIC_API_KEY   key for the LLM calls (Azure Foundry key)
    ANTHROPIC_ENDPOINT  Foundry base URL, e.g. https://<res>.services.ai.azure.com/anthropic
    DEFAULT_MODEL       model id / deployment name (default 'claude-sonnet-5')
    ANTHROPIC_MAX_TOKENS  cap on generation tokens (default 8000)
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
logger = logging.getLogger("validation_rules_generator")


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
# Foundry base URL, e.g. https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_ENDPOINT = os.environ.get("ANTHROPIC_ENDPOINT") or None
# int() on an empty string throws, so fall back when the env value is blank.
MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS") or "8000")

IN_REQUIREMENTS = "extracted_requirements.json"
IN_OPENAPI = "openapi.yaml"
IN_PAYLOADS = "sample-payloads.json"
IN_SCHEMA = "db_schema.json"

OUT_JSON = "validation-rules.json"


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------
def resolve_shared_dir(cli_dir: str | None) -> Path:
    raw = cli_dir or os.environ.get(ENV_VAR)
    if not raw:
        raise SystemExit(
            f"No location set. Set {ENV_VAR} (the folder with the artifacts) "
            f"or pass --dir."
        )
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise SystemExit(f"{ENV_VAR} is not a directory: {p}")
    return p


def load_inputs(shared: Path) -> dict:
    """Read the artifacts this agent needs. openapi.yaml is required; the DB
    schema and sample payloads are strongly recommended (mirroring §8 and
    sanity-checking values) but the agent degrades gracefully if absent."""
    def read_json(name: str, required: bool) -> Any:
        f = shared / name
        if not f.is_file():
            if required:
                raise SystemExit(f"Missing input: {f}. Run the upstream agents first.")
            logger.warning("Optional input not found, continuing without it: %s", f)
            return {}
        return json.loads(f.read_text(encoding="utf-8"))

    openapi_path = shared / IN_OPENAPI
    if not openapi_path.is_file():
        raise SystemExit(f"Missing input: {openapi_path}. Run the API-contract agent first.")
    try:
        import yaml
    except ImportError:
        raise SystemExit("The 'pyyaml' package is required to read openapi.yaml. pip install pyyaml")
    openapi = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))

    return {
        "extracted_requirements": read_json(IN_REQUIREMENTS, required=False),
        "openapi": openapi,
        "sample_payloads": read_json(IN_PAYLOADS, required=False),
        "db_schema": read_json(IN_SCHEMA, required=False),
    }


# ---------------------------------------------------------------------------
# Distillation helpers
# ---------------------------------------------------------------------------
def _resolve_ref(ref: str, schemas: dict) -> dict:
    """Resolve a local component $ref like '#/components/schemas/Address'."""
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, {})


def _flatten_schema(node: dict, schemas: dict, depth: int = 0) -> dict:
    """Reduce an OpenAPI schema node to the fields relevant to validation,
    inlining $refs up to a small depth so nested objects (e.g. address) are
    visible to the model without blowing up the prompt."""
    if not isinstance(node, dict):
        return {}
    if "$ref" in node and depth < 2:
        return _flatten_schema(_resolve_ref(node["$ref"], schemas), schemas, depth + 1)

    out: dict = {}
    for key in ("type", "format", "enum", "minimum", "maximum", "minLength",
                "maxLength", "pattern", "minItems", "maxItems"):
        if key in node:
            out[key] = node[key]

    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        out["items"] = _flatten_schema(node["items"], schemas, depth + 1)

    props = node.get("properties")
    if isinstance(props, dict):
        req = set(node.get("required", []))
        fields = {}
        for fname, fschema in props.items():
            fdesc = _flatten_schema(fschema, schemas, depth + 1)
            if fname in req:
                fdesc["required"] = True
            fields[fname] = fdesc
        out["properties"] = fields
        if req:
            out["required"] = sorted(req)
    return out


def _request_endpoints(openapi: dict) -> dict:
    """Map each *Request component schema -> the endpoint(s) that consume it,
    so the model can write endpoint-aware messages."""
    mapping: dict[str, str] = {}
    for path, ops in (openapi.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        for method, op in ops.items():
            if not isinstance(op, dict):
                continue
            body = (op.get("requestBody") or {}).get("content", {})
            for media in body.values():
                ref = (media.get("schema") or {}).get("$ref")
                if ref:
                    mapping.setdefault(ref.rsplit("/", 1)[-1], f"{method.upper()} {path}")
    return mapping


def _db_constraint_index(db_schema: dict) -> dict:
    """Flatten §8 into {fieldName: {required, unique, enum, type, collection}} so
    the model can mirror DB constraints onto the matching form fields by name."""
    index: dict[str, dict] = {}
    collections = db_schema.get("collections") or db_schema.get("tables") or []
    for coll in collections:
        cname = coll.get("name", "")

        def walk(fields: list):
            for f in fields:
                nm = f.get("name")
                if nm and nm not in index:
                    entry = {"collection": cname, "type": f.get("type")}
                    for k in ("required", "unique", "enum"):
                        if f.get(k) not in (None, False):
                            entry[k] = f[k]
                    index[nm] = entry
                if f.get("fields"):
                    walk(f["fields"])

        walk(coll.get("fields", []) or coll.get("columns", []))
    return index


def _texts(items: list) -> list[str]:
    out: list[str] = []
    for it in items or []:
        if isinstance(it, dict):
            t = it.get("text") or it.get("name") or ""
            if t:
                out.append(str(t))
        elif it:
            out.append(str(it))
    return out


def distill(inputs: dict) -> dict:
    """Pull just the validation-relevant facts, to keep the prompt focused."""
    openapi = inputs["openapi"]
    schemas = (openapi.get("components") or {}).get("schemas", {})
    endpoints = _request_endpoints(openapi)

    # Every input FORM the user fills in == a *Request schema.
    forms: dict[str, dict] = {}
    for name, node in schemas.items():
        if not name.endswith("Request"):
            continue
        flat = _flatten_schema(node, schemas)
        forms[name] = {
            "endpoint": endpoints.get(name, ""),
            "required": flat.get("required", []),
            "fields": flat.get("properties", {}),
        }

    # Compact example request bodies keyed by operationId (only those with a body).
    examples = {}
    for op, spec in (inputs.get("sample_payloads") or {}).items():
        if isinstance(spec, dict) and spec.get("request"):
            examples[op] = {
                "endpoint": f'{spec.get("method","")} {spec.get("path","")}'.strip(),
                "request": spec["request"],
            }

    er = inputs.get("extracted_requirements") or {}
    return {
        "forms": forms,
        "db_constraints": _db_constraint_index(inputs.get("db_schema") or {}),
        "sample_requests": examples,
        "domain_rules": (
            _texts(er.get("business_rules", []))
            + _texts(er.get("constraints", []))
            + _texts(er.get("functional", []))[:20]
        ),
    }


# ---------------------------------------------------------------------------
# LLM plumbing (patchable for testing)
# ---------------------------------------------------------------------------
def _client():
    """Build an Azure AI Foundry client, matching the sibling agents' pattern."""
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
# Prompt
# ---------------------------------------------------------------------------
GENERATE_SYSTEM = """You are a senior frontend engineer writing the client-side \
validation rules for an application's input forms. For every form field you emit the \
EXACT validation rule and the EXACT human-readable message the user sees when the \
field is invalid.

You are given, per form: its endpoint, the request schema (fields with type/format/ \
enum/required/min/max) and — separately — a flat index of the datastore constraints \
from §8 (required / unique / enum / type per field) and some example payloads.

Rules for your output:
- MIRROR THE DB CONSTRAINTS FROM §8. If a field is `required`/`unique`/has an `enum` \
in the DB index (matched by field name), reflect that in the field's rule. The DB is \
the source of truth for required-ness and allowed values.
- Choose the right rule keys per field: `required` (bool), `type` \
("email"|"tel"|"string"|"number"|"integer"|"boolean"|"url"|"date"|"array"), `min` / \
`max` (for number ranges OR string length — use `min`/`max` for numbers and \
`minLength`/`maxLength` for strings), `enum` (allowed values), `pattern` (regex as a \
string), `matches` (name of another field this must equal). Only include keys that \
apply.
- ADD UI-ONLY FIELDS the API cannot express. For any form that sets or resets a \
password, add a `confirm` field: {"matches": "<the password field>", "message": \
"Passwords do not match."}. Use the actual password field name present in that form \
(e.g. "password" or "newPassword").
- DERIVE SENSIBLE CONSTRAINTS from the domain rules and security requirements even \
when the schema omits them — e.g. a minimum password length of 8, phone as type \
"tel", email as type "email", ratings within their documented range, monetary and \
quantity fields as non-negative numbers.
- EVERY field rule MUST include a concise, user-facing `message` written in plain \
sentence case ending with a period (e.g. "Enter a valid email address.", "Password \
must be at least 8 characters."). The message must describe the specific failing \
rule, not be generic.
- Key each form by its friendly operationId when one exists in the example payloads \
(e.g. "registerUser", "resetPassword"); otherwise use the request-schema name.
- Only include forms that have user-editable fields worth validating; skip empty \
request bodies.

Respond with STRICT JSON only, no prose, no markdown fences. Shape:
{
  "<formKey>": {
    "<fieldName>": { "required": true, "type": "email", "message": "Enter a valid email address." },
    "<fieldName>": { "required": true, "minLength": 8, "message": "Password must be at least 8 characters." },
    "confirm":     { "matches": "password", "message": "Passwords do not match." }
  }
}"""


# ---------------------------------------------------------------------------
# The reasoning step
# ---------------------------------------------------------------------------
def generate_rules(inputs: dict) -> dict:
    """Core: distill the artifacts -> ask the model for the validation rules."""
    facts = distill(inputs)
    logger.info("Deriving validation rules for %d forms (model=%s)...",
                len(facts["forms"]), MODEL)
    user = (
        "Design inputs:\n```json\n"
        + json.dumps(facts, indent=2, ensure_ascii=False, default=str)
        + "\n```\nProduce the per-field validation rules, mirroring the DB "
          "constraints from §8 and adding UI-only fields (e.g. confirm password)."
    )
    rules = _call_json(GENERATE_SYSTEM, user, max_tokens=MAX_TOKENS)
    return rules


# ---------------------------------------------------------------------------
# Deterministic normalisation (no LLM) — keeps validation-rules.json well-formed
# ---------------------------------------------------------------------------
_HUMAN = re.compile(r"(?<!^)(?=[A-Z])")


def _humanize(field: str) -> str:
    """confirmPassword -> 'Confirm password'; first_name -> 'First name'."""
    s = _HUMAN.sub(" ", field.replace("_", " ")).strip()
    return (s[:1].upper() + s[1:].lower()) if s else field


def _default_message(field: str, rule: dict) -> str:
    """Synthesize a reasonable message if the model omitted one."""
    label = _humanize(field)
    if "matches" in rule:
        return f"{label} does not match."
    if rule.get("type") == "email":
        return "Enter a valid email address."
    if rule.get("type") in ("tel", "phone"):
        return "Enter a valid phone number."
    for k in ("minLength", "min"):
        if k in rule:
            return f"{label} must be at least {rule[k]} characters."
    if "enum" in rule:
        return f"{label} must be one of: {', '.join(map(str, rule['enum']))}."
    if rule.get("required"):
        return f"{label} is required."
    return f"{label} is invalid."


def normalise_rules(rules: dict) -> tuple[dict, list[str]]:
    """Guarantee every field rule has a message; drop obviously-empty forms."""
    warnings: list[str] = []
    clean: dict = {}
    for form, fields in (rules or {}).items():
        if not isinstance(fields, dict) or not fields:
            warnings.append(f"form '{form}' had no fields and was dropped")
            continue
        out: dict = {}
        for field, rule in fields.items():
            if not isinstance(rule, dict):
                warnings.append(f"'{form}.{field}' rule was not an object; skipped")
                continue
            if not str(rule.get("message", "")).strip():
                rule["message"] = _default_message(field, rule)
                warnings.append(f"'{form}.{field}' had no message; a default was filled in")
            out[field] = rule
        clean[form] = out
    return clean, warnings


# ---------------------------------------------------------------------------
# Light deterministic self-validation (warnings only)
# ---------------------------------------------------------------------------
def validate_rules(rules: dict, inputs: dict) -> list[str]:
    warnings: list[str] = []
    if not rules:
        warnings.append("no validation rules were produced")
    # A password-creation/reset form should carry a matching confirm field.
    # Login/authenticate forms take a password but must NOT ask to confirm it.
    for form, fields in rules.items():
        is_auth = re.search(r"(?i)login|log[\s_-]?in|authenticate|signin", form)
        sets_pw = any(re.search(r"(?i)register|signup|sign[\s_-]?up|reset|change", form)
                      or k in ("newPassword",) for k in [form] + list(fields))
        has_pw = any(k.lower().endswith("password") for k in fields)
        has_confirm = any("matches" in v for v in fields.values() if isinstance(v, dict))
        if has_pw and sets_pw and not is_auth and not has_confirm:
            warnings.append(f"form '{form}' sets a password but has no confirm/matches field")
    return warnings


# ---------------------------------------------------------------------------
# Writing outputs
# ---------------------------------------------------------------------------
def write_outputs(shared: Path, rules: dict) -> dict:
    path = shared / OUT_JSON
    path.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"json": str(path)}


# ---------------------------------------------------------------------------
# Reusable core used by BOTH entrypoints
# ---------------------------------------------------------------------------
def run(shared_dir: str | None = None, inputs: dict | None = None) -> dict:
    """Resolve dir -> load inputs -> generate -> normalise -> write -> return."""
    load_dotenv_files()
    shared = resolve_shared_dir(shared_dir)
    if inputs is None:
        inputs = load_inputs(shared)
    raw = generate_rules(inputs)
    rules, warnings = normalise_rules(raw)
    warnings += validate_rules(rules, inputs)
    paths = write_outputs(shared, rules)
    n = sum(len(f) for f in rules.values())
    logger.info("Validation rules generated: %d fields across %d forms -> %s",
                n, len(rules), paths["json"])
    return {"validation_rules": rules, "warnings": warnings, "paths": paths}


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------
def validation_rules_node(state: dict) -> dict:
    """LangGraph node. Reads `shared_dir` (and optional preloaded `inputs`) from
    state; returns the validation-rules artifacts to merge back into state.

    Example:
        from langgraph.graph import StateGraph
        graph = StateGraph(dict)
        graph.add_node("validation_rules", validation_rules_node)
        # state = {"shared_dir": "/path/to/shared"}
    """
    shared_dir = state.get("shared_dir") or state.get("SHARED_DIR")
    inputs = state.get("inputs")  # optional: pass artifacts directly to skip disk read
    result = run(shared_dir=shared_dir, inputs=inputs)
    return {
        "validation_rules": result["validation_rules"],
        "validation_rules_paths": result["paths"],
        "validation_rules_warnings": result["warnings"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Generate per-field validation rules (D4) from the design artifacts")
    ap.add_argument("--dir", default=None,
                    help=f"shared folder (inputs in, outputs out). Overrides ${ENV_VAR}.")
    args = ap.parse_args()

    result = run(shared_dir=args.dir)
    rules = result["validation_rules"]
    n = sum(len(f) for f in rules.values())
    print(f"Forms: {len(rules)}  Fields: {n} -> {result['paths']['json']}")
    for w in result["warnings"]:
        print(f"  [warn] {w}")


if __name__ == "__main__":
    main()
