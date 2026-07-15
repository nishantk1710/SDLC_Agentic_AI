#!/usr/bin/env python3
"""
api_contract_generator.py  —  Level-4 API Contract agent

Consumes the earlier artifacts from the shared folder and produces the backend
API contract (handoff item #5: D2 API Specification + D5 Sample Payloads):

    extracted_requirements.json   (functional reqs, roles, constraints, auth needs)
    db_schema.json                (entities/collections/tables -> resource schemas)
    backend-structure.json        (feature modules -> endpoint grouping / tags)
    user_features.json            (OPTIONAL — feature descriptions for endpoint intent)
    routes.json                   (OPTIONAL — frontend routes, to ensure the API
                                   serves what the UI actually needs)
        ->  openapi.yaml              (OpenAPI 3.1 spec: every endpoint, typed
                                       request/response, error shapes, per-endpoint
                                       auth, with realistic `examples:` embedded)
            sample-payloads.json      (companion: named request/response samples)
            api_contract_decision.md  (approaches compared + chosen + why)

Reasoning style (same as the schema / backend agents):
    1. DELIBERATE — study the resources, features and constraints; propose 2-3
       genuinely different API-design approaches with concrete pros/cons.
    2. DECIDE     — pick the best for THIS app, with a rationale.
    3. GENERATE   — emit the concrete contract (endpoints + schemas + examples).

The model designs the contract as STRUCTURED JSON (judgement); the agent renders
the OpenAPI YAML deterministically so the document is always well-formed and the
examples always line up with the schemas.

Two entrypoints, one core:
    • CLI:        python api_contract_generator.py         (uses $SHARED_DIR)
    • LangGraph:  from api_contract_generator import api_contract_node
                  graph.add_node("api_contract", api_contract_node)

Environment (shared with the other agents):
    SHARED_DIR, ANTHROPIC_API_KEY, ANTHROPIC_ENDPOINT, DEFAULT_MODEL,
    ANTHROPIC_MAX_TOKENS  — identical conventions to schema_generator.py.
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
logger = logging.getLogger("api_contract_generator")


def load_dotenv_files() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env", override=False)
    load_dotenv(override=False)


load_dotenv_files()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENV_VAR = "SHARED_DIR"
MODEL = os.environ.get("DEFAULT_MODEL") or "claude-sonnet-5"
ANTHROPIC_ENDPOINT = os.environ.get("ANTHROPIC_ENDPOINT") or None
MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS") or "8000")
# Per-generation output cap. Sized so a single call reliably COMPLETES within the
# HTTP timeout on a slow endpoint; if the contract needs more, truncation trips
# the batched fallback (smaller, faster calls) rather than a giant slow request.
CONTRACT_MAX_TOKENS = int(os.environ.get("API_CONTRACT_MAX_TOKENS") or "12000")
# The skeleton (all component schemas + a terse endpoint index, NO examples) is
# the one inherently large batched call. Give it a generous budget so it finishes
# in ONE call instead of truncating and retrying — a truncated attempt is pure
# wasted time and tokens. A cap is only a ceiling; you pay for tokens generated,
# so sizing it high is cost-neutral and just avoids the retry.
SKELETON_MAX_TOKENS = int(os.environ.get("API_CONTRACT_SKELETON_MAX_TOKENS") or "48000")
# Per-tag endpoint calls are independent, so they can run concurrently. This is
# the biggest wall-clock win on a slow endpoint. Set to 1 to go sequential if the
# endpoint rate-limits. Does NOT change cost (same calls/tokens), only latency.
TAG_CONCURRENCY = max(1, int(os.environ.get("API_CONTRACT_TAG_CONCURRENCY") or "4"))
# Cap how many endpoints one per-call request must detail. A tag with many
# endpoints (e.g. 18) can overflow CONTRACT_MAX_TOKENS in a single call and
# truncate; chunking keeps every call comfortably within budget (and, since
# chunks are independent, increases parallelism). If a chunk still truncates it
# is split in half automatically, so generation always converges.
ENDPOINTS_PER_CALL = max(1, int(os.environ.get("API_CONTRACT_ENDPOINTS_PER_CALL") or "8"))
# The single-shot attempt almost always truncates for a real-sized API (wasting a
# ~2-minute call before the batched path takes over), so it's OFF by default: we
# go straight to batched. Set API_CONTRACT_SINGLE_SHOT=1 to try one-shot first
# (worthwhile only for very small APIs that fit in a single response).
SINGLE_SHOT = (os.environ.get("API_CONTRACT_SINGLE_SHOT") or "0") not in ("0", "false", "False")
# A large generation can take minutes; the SDK default (600s) is fine, but make
# it explicit and configurable. max_retries=1: a timed-out big request should
# fall back to batched calls, not silently re-bill 2-3 full generations.
HTTP_TIMEOUT = float(os.environ.get("API_CONTRACT_TIMEOUT") or "600")
MAX_RETRIES = int(os.environ.get("API_CONTRACT_MAX_RETRIES") or "1")

IN_REQUIREMENTS = "extracted_requirements.json"
IN_SCHEMA = "db_schema.json"
IN_BACKEND = "backend-structure.json"
IN_FEATURES = "user_features.json"          # optional
IN_ROUTES = "routes.json"                   # optional

OUT_YAML = "openapi.yaml"
OUT_SAMPLES = "sample-payloads.json"
OUT_DECISION = "api_contract_decision.md"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def resolve_shared_dir(cli_dir: str | None) -> Path:
    raw = cli_dir or os.environ.get(ENV_VAR)
    if not raw:
        raise SystemExit(f"No location set. Set {ENV_VAR} (the folder with the "
                         f"earlier artifacts) or pass --dir.")
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
        "db_schema": read(IN_SCHEMA),
        "backend_structure": read(IN_BACKEND),
        "user_features": read(IN_FEATURES, required=False),
        "routes": read(IN_ROUTES, required=False),
    }


def _resource_names(schema: dict) -> list[str]:
    """Top-level resource names from whatever datastore shape the schema used."""
    if isinstance(schema.get("tables"), list):
        return [t.get("name") for t in schema["tables"]]
    if isinstance(schema.get("collections"), list):
        return [c.get("model") or c.get("name") for c in schema["collections"]]
    if isinstance(schema.get("entities"), list):
        return list(schema["entities"])
    return []


def _backend_modules(backend: dict) -> list[str]:
    """Feature/module names from backend-structure.json, for endpoint grouping."""
    if not isinstance(backend, dict):
        return []
    tree = backend.get("tree", backend)
    if not isinstance(tree, dict):
        return []
    for container in ("modules/", "features/", "controllers/", "routes/"):
        for k, v in tree.items():
            if k == container and isinstance(v, dict):
                return [x.rstrip("/") for x in v]
            if isinstance(v, dict) and container in v and isinstance(v[container], dict):
                return [x.rstrip("/") for x in v[container]]
    return []


def _extract_routes(routes) -> list:
    """Compact frontend route list, tolerant of shape (see backend agent)."""
    if not routes:
        return []
    items = routes if isinstance(routes, list) else \
        (routes.get("routes") if isinstance(routes, dict) and isinstance(routes.get("routes"), list)
         else ([{"path": k, **(v if isinstance(v, dict) else {})}
                for k, v in routes.items()] if isinstance(routes, dict) else []))
    out = []
    for r in items:
        if isinstance(r, str):
            out.append({"path": r})
        elif isinstance(r, dict):
            keep = {k: r[k] for k in ("path", "name", "role", "roles", "access", "protected") if k in r}
            if keep:
                out.append(keep)
    return out


def _resource_fields(schema: dict) -> dict:
    """Compact {ResourceName: [{name, type, required, enum?}]} for typing the API.
    Drops indexes, comments, defaults, examples and deep nesting — the API
    contract only needs field names + types, so this is far cheaper than the
    whole schema while preserving what the generate step actually uses."""
    def field_of(f: dict) -> dict:
        t = str(f.get("type", "string"))
        # flatten embedded subdocuments/arrays to a coarse type to stay compact
        if f.get("fields") or t.lower() in ("object", "[object]", "subdocument"):
            t = "array" if t.startswith("[") else "object"
        rec = {"name": f.get("name"), "type": t}
        if f.get("required"):
            rec["required"] = True
        if f.get("enum"):
            rec["enum"] = f["enum"]
        return rec

    out: dict = {}
    if isinstance(schema.get("collections"), list):
        for c in schema["collections"]:
            name = c.get("model") or c.get("name")
            out[name] = [field_of(f) for f in c.get("fields", [])]
    elif isinstance(schema.get("tables"), list):
        for t in schema["tables"]:
            out[t.get("name")] = [
                {"name": col.get("name"), "type": col.get("type", "string"),
                 **({"required": True} if not col.get("nullable", True) else {})}
                for col in t.get("columns", [])]
    else:
        for e in schema.get("entities", []):
            out[e] = []
    return out


def _role_enum_values(schema: dict) -> list:
    """Collect enum values from any field/column named 'role' (or 'roles') across
    the schema, whatever the datastore shape. These are the machine role values
    the API's per-endpoint 'roles' will use."""
    vals: set = set()

    def scan_fields(fields):
        for f in fields or []:
            nm = str(f.get("name", "")).lower()
            if nm in ("role", "roles") and isinstance(f.get("enum"), list):
                vals.update(f["enum"])
            if f.get("fields"):
                scan_fields(f["fields"])

    for c in schema.get("collections", []) or []:
        scan_fields(c.get("fields"))
    for t in schema.get("tables", []) or []:
        for col in t.get("columns", []) or []:
            nm = str(col.get("name", "")).lower()
            if nm in ("role", "roles") and isinstance(col.get("enum"), list):
                vals.update(col["enum"])
    return sorted(vals)


def distill(inputs: dict) -> dict:
    """Pull just what shapes an API contract, keeping the prompt focused."""
    er = inputs["extracted_requirements"] or {}
    schema = inputs["db_schema"] or {}
    backend = inputs["backend_structure"] or {}
    uf = inputs["user_features"] or {}
    return {
        "functional_requirements": er.get("functional", []),
        "business_rules": er.get("business_rules", []),
        "non_functional": er.get("non_functional", []),
        "constraints": er.get("constraints", []),
        "external_interfaces": er.get("external_interfaces", []),
        "tech_stack": er.get("tech_stack", []),
        "roles": [r.get("role") for r in uf.get("roles", [])],
        # The machine role values the schema actually declares (e.g. a User.role
        # enum). The contract's per-endpoint roles use THESE, so the validator must
        # accept them too — the user_features labels ("Platform Administrator") and
        # the schema enum ("platformAdmin") are different spellings of the same role.
        "role_values": _role_enum_values(schema),
        "features": [{"name": f.get("name"), "description": f.get("description")}
                     for f in uf.get("features", [])],
        "resources": _resource_names(schema),
        # Compact field map instead of the full schema (big input-token saving).
        "resource_fields": _resource_fields(schema),
        "backend_modules": _backend_modules(backend),
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
        raise SystemExit("ANTHROPIC_ENDPOINT is empty. Set it to your Foundry base URL (…/anthropic).")
    # A large contract can take several minutes to generate, so the default
    # 180s timeout trips and the SDK silently retries (each retry costing another
    # full generation). Give it real headroom and don't retry a timed-out big
    # request — surfacing it lets us fall back to the smaller batched calls.
    return AnthropicFoundry(api_key=api_key, base_url=ANTHROPIC_ENDPOINT,
                            timeout=HTTP_TIMEOUT, max_retries=MAX_RETRIES)



class TruncatedResponse(Exception):
    """Raised when the model hit max_tokens before finishing its JSON."""


# Prompt caching: the big system prompts are identical every run (and reused on
# each per-tag batch call), so caching them cuts input-token cost. Off unless the
# endpoint supports it; a failed cached call transparently falls back to a plain
# one, so this can never break a working setup.
# Prompt caching is OFF by default: on endpoints that don't support cache blocks
# the probe call can hang until timeout, wasting minutes. Turn on only if your
# endpoint supports it (API_CONTRACT_CACHE_PROMPTS=1) to save repeated input tokens.
CACHE_PROMPTS = (os.environ.get("API_CONTRACT_CACHE_PROMPTS") or "0") not in ("0", "false", "False")
_CACHE_DISABLED = False   # set once at runtime if the endpoint rejects cache blocks


def _create(system: str, user: str, max_tokens: int):
    global _CACHE_DISABLED
    client = _client()
    if CACHE_PROMPTS and not _CACHE_DISABLED:
        try:
            return client.messages.create(
                model=MODEL, max_tokens=max_tokens,
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
            )
        except Exception as e:               # endpoint doesn't accept cache blocks
            _CACHE_DISABLED = True
            logger.info("Prompt caching unsupported here (%s); continuing without it.",
                        type(e).__name__)
    return client.messages.create(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )


def _call_json(system: str, user: str, max_tokens: int = MAX_TOKENS) -> dict:
    resp = _create(system, user, max_tokens)
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if getattr(resp, "stop_reason", None) == "max_tokens":
        # incomplete JSON — surface it clearly instead of a cryptic decode error
        raise TruncatedResponse(text)
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                raise TruncatedResponse(text)   # likely an incomplete object
        raise


# ---------------------------------------------------------------------------
# Prompts (domain-neutral; stack-aware from the inputs)
# ---------------------------------------------------------------------------
DELIBERATE_SYSTEM = """You are a senior API architect. Given an application's \
resources, features, business rules, roles and constraints, reason about how best \
to design its backend HTTP API.

Propose 2-3 GENUINELY DIFFERENT design approaches (not trivial variants). Consider \
axes such as: resource-oriented REST (nouns + HTTP verbs) vs. action/RPC-style \
endpoints vs. a hybrid (REST for CRUD, action sub-resources for state transitions \
like accept/cancel/assign); how nested vs. flat the resource paths are; how \
filtering, pagination and sorting are expressed; how state-machine transitions are \
modelled; and how auth/roles gate endpoints. For each approach give concrete pros \
and cons FOR THIS APP. Then pick the best and justify it briefly.

Respond with STRICT JSON only, no prose, no markdown fences:
{
  "approaches": [
    {"name": "...", "summary": "...", "pros": ["..."], "cons": ["..."]}
  ],
  "chosen": "<name of the chosen approach>",
  "rationale": "<why this is best for this app>"
}"""

GENERATE_SYSTEM = """You are a senior API architect implementing the chosen design. \
Produce the concrete API contract as STRUCTURED JSON that will be rendered into an \
OpenAPI 3.1 document. Design against the app's ACTUAL resources, features, business \
rules, roles and datastore.

Rules:
- Cover EVERY resource and every functional requirement with endpoints: list/create \
on collections, read/update/delete on items, plus action sub-resources for state \
transitions (e.g. /orders/{id}/accept) where the requirements imply them.
- Use consistent plural, lowercase, hyphenated resource paths and path params like \
{id}. Group endpoints with a `tag` aligned to the backend modules when provided.
- Every operation: method, path, summary, path/query params (typed), request body \
schema (where applicable), success response schema, and the error responses it can \
return (reference shared error components). Give each request and main success \
response a realistic `example` drawn from the domain (NOT lorem ipsum).
- Model auth per operation: set "security" true/false and list allowed "roles" for \
protected operations, matching the app's roles. Public endpoints set security false.
- Define reusable component schemas for each resource (fields + types from the \
provided `resource_fields` map; do not leak DB-internal-only fields like password \
hashes into responses), plus shared schemas: a standard Error shape and a \
Pagination wrapper.
- Money as string-decimal; ids as string; timestamps as date-time. Do NOT invent \
resources or fields beyond those implied by the inputs.
- If `frontend_routes` are provided, make sure the API serves the data those routes \
need; treat them as coverage hints, not endpoints to copy verbatim.

Respond with STRICT JSON only, no prose, no markdown fences, in this shape:
{
  "info": {"title": "<app> API", "version": "1.0.0", "description": "..."},
  "servers": ["https://api.example.com/v1"],
  "security_schemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
  "tags": [{"name": "orders", "description": "..."}],
  "components": {
    "Error": {"type": "object", "properties": {"code": {"type": "string"}, "message": {"type": "string"}, "details": {"type": "object"}}, "required": ["code", "message"]},
    "<ResourceName>": {"type": "object", "properties": {"id": {"type": "string"}, "...": {"...": "..."}}, "required": ["id"], "example": {"id": "..."}}
  },
  "endpoints": [
    {
      "tag": "orders",
      "method": "post",
      "path": "/orders",
      "operationId": "createOrder",
      "summary": "Place a new order",
      "security": true,
      "roles": ["customer"],
      "path_params": [],
      "query_params": [{"name": "expand", "type": "string", "required": false, "description": "..."}],
      "request": {"schema_ref": "CreateOrderRequest", "example": {"restaurantId": "r_123", "items": []}},
      "responses": [
        {"status": "201", "schema_ref": "Order", "description": "Created", "example": {"id": "o_1", "status": "pendingRestaurantAcceptance"}},
        {"status": "400", "schema_ref": "Error", "description": "Validation failed"},
        {"status": "401", "schema_ref": "Error", "description": "Unauthenticated"}
      ]
    }
  ]
}
Define any request-body schemas you reference (e.g. CreateOrderRequest) inside \
"components" too. Keep examples realistic and internally consistent with the schemas."""


# Batched fallback: used automatically when the single-shot contract would be too
# large for one response. Splits generation into a skeleton call + per-tag calls.
GENERATE_SKELETON_SYSTEM = """You are a senior API architect. Produce ONLY the \
non-endpoint parts of the API contract, plus a compact index of endpoints (no \
per-endpoint detail yet). Follow the same design rules and resource coverage as a \
full contract.

Respond with STRICT JSON only, no prose, no fences:
{
  "info": {"title": "...", "version": "1.0.0", "description": "..."},
  "servers": ["https://api.example.com/v1"],
  "security_schemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
  "tags": [{"name": "orders", "description": "..."}],
  "components": { "Error": {"...": "..."}, "<Resource>": {"...": "..."} },
  "endpoint_index": [
    {"tag": "orders", "method": "post", "path": "/orders", "operationId": "createOrder", "summary": "...", "security": true, "roles": ["customer"]}
  ]
}
Define ALL component schemas here (resource schemas + request-body schemas + Error \
+ a Pagination wrapper). The endpoint_index must list EVERY endpoint (all CRUD, all \
state-transition actions) but with no params/request/response detail.

CRITICAL to keep this response small enough to finish:
- Do NOT put any "example" blocks in the components — examples are added later at \
the endpoint level. Schemas here are property names + types + enums + required only.
- Keep every "description" to at most a short phrase, or omit it.
- For a $ref, ALWAYS write the full path "#/components/schemas/<Name>"."""

GENERATE_ENDPOINTS_SYSTEM = """You are a senior API architect. Given the already- \
decided component schemas (by name) and a list of endpoints for ONE tag, produce the \
FULL detail for each of those endpoints: params (typed), request body schema_ref + \
realistic example, and responses (success schema_ref + realistic example, plus the \
error responses referencing the Error schema). Only reference schema names that \
exist in the provided list.

Respond with STRICT JSON only, no prose, no fences:
{
  "endpoints": [
    {"tag": "...", "method": "...", "path": "...", "operationId": "...", "summary": "...",
     "security": true, "roles": ["..."], "path_params": [], "query_params": [],
     "request": {"schema_ref": "...", "example": {}},
     "responses": [{"status": "200", "schema_ref": "...", "description": "...", "example": {}},
                   {"status": "400", "schema_ref": "Error", "description": "..."}]}
  ]
}"""


# ---------------------------------------------------------------------------
# Reasoning steps
# ---------------------------------------------------------------------------
def deliberate(facts: dict) -> dict:
    # deliberation only compares approaches: it needs resource NAMES, roles and
    # requirements — not the per-field map. Dropping it keeps this call cheap.
    light = {k: v for k, v in facts.items() if k != "resource_fields"}
    user = ("Application facts:\n```json\n"
            + json.dumps(light, indent=2, ensure_ascii=False)
            + "\n```\nPropose API-design approaches, compare, and choose one.")
    return _call_json(DELIBERATE_SYSTEM, user, max_tokens=2500)


def _facts_and_choice(facts: dict, decision: dict) -> str:
    return ("Application facts:\n```json\n"
            + json.dumps(facts, indent=2, ensure_ascii=False)
            + "\n```\n\nChosen approach:\n```json\n"
            + json.dumps({"chosen": decision.get("chosen"),
                          "rationale": decision.get("rationale")}, indent=2, ensure_ascii=False)
            + "\n```\n")


def _design_batched(facts: dict, decision: dict) -> dict:
    """Large-API path: one skeleton call (all schemas + a terse endpoint index),
    then per-tag endpoint detail. Per-tag calls run concurrently (independent),
    which is the main wall-clock win on a slow endpoint."""
    logger.info("Generating contract via batched path (skeleton + per-tag)...")
    skel_prompt = _facts_and_choice(facts, decision) + "Produce the skeleton."
    try:
        # Generous skeleton budget so it completes in ONE call (no truncate+retry).
        skeleton = _call_json(GENERATE_SKELETON_SYSTEM, skel_prompt, max_tokens=SKELETON_MAX_TOKENS)
    except TruncatedResponse:
        # Safety net only — should be rare now that the budget is sized up front.
        logger.info("Skeleton truncated; retrying at the max budget...")
        skeleton = _call_json(GENERATE_SKELETON_SYSTEM, skel_prompt, max_tokens=64000)
    index = skeleton.pop("endpoint_index", [])
    # Normalise the component block up front: if the model returned the canonical
    # {"schemas": {...}} nesting, unwrap it so the per-tag calls below are told the
    # REAL schema names (User, Order, ...) rather than the single key "schemas".
    skeleton["components"] = _normalize_components(skeleton.get("components"))
    schema_names = sorted(skeleton.get("components", {}).keys())
    # group endpoints by tag, preserving first-seen order
    by_tag: dict[str, list] = {}
    for ep in index:
        by_tag.setdefault(ep.get("tag", "default"), []).append(ep)

    # Per-tag calls only need a COMPACT context (chosen approach, roles, field
    # map + defined schema names) — not the full requirements/routes payload.
    # This avoids resending the whole facts blob N times (big token saving).
    compact_ctx = ("Context:\n```json\n" + json.dumps({
        "chosen": decision.get("chosen"),
        "roles": facts.get("roles", []),
        "resource_fields": facts.get("resource_fields", {}),
    }, indent=2, ensure_ascii=False) + "\n```\n")

    def _gen_chunk(tag: str, eps: list) -> list:
        """Detail one chunk of a tag's endpoints. Resilient to truncation: if the
        response is cut off, split the chunk in half and retry each half (a single
        endpoint that still won't fit is retried once at a larger budget). This
        guarantees the run completes instead of aborting and losing all work."""
        payload = {"tag": tag, "available_schema_names": schema_names, "endpoints": eps}
        prompt = (compact_ctx
                  + "Endpoints to detail (for this tag only):\n```json\n"
                  + json.dumps(payload, indent=2, ensure_ascii=False) + "\n```")
        try:
            return _call_json(GENERATE_ENDPOINTS_SYSTEM, prompt,
                              max_tokens=CONTRACT_MAX_TOKENS).get("endpoints", [])
        except TruncatedResponse:
            if len(eps) > 1:
                mid = len(eps) // 2
                logger.info("  chunk of %d for '%s' truncated; splitting into %d + %d",
                            len(eps), tag, mid, len(eps) - mid)
                return _gen_chunk(tag, eps[:mid]) + _gen_chunk(tag, eps[mid:])
            # a single endpoint that still overflowed — one retry at a bigger budget
            logger.info("  single endpoint for '%s' truncated; retrying larger", tag)
            return _call_json(GENERATE_ENDPOINTS_SYSTEM, prompt,
                              max_tokens=min(CONTRACT_MAX_TOKENS * 3, 48000)).get("endpoints", [])

    # Build ordered work units: (tag, endpoint-chunk). Chunking bounds each call's
    # output so it can't overflow, and yields more independent units to parallelise.
    tags = list(by_tag.items())
    units: list[tuple[int, str, list]] = []
    for tag, eps in tags:
        for i in range(0, len(eps), ENDPOINTS_PER_CALL):
            units.append((len(units), tag, eps[i:i + ENDPOINTS_PER_CALL]))

    results: dict[int, list] = {}
    if TAG_CONCURRENCY > 1 and len(units) > 1:
        from concurrent.futures import ThreadPoolExecutor
        logger.info("Detailing %d endpoint(s) across %d call(s), concurrency=%d...",
                    sum(len(e) for _, e in tags), len(units), TAG_CONCURRENCY)
        with ThreadPoolExecutor(max_workers=TAG_CONCURRENCY) as pool:
            futs = {pool.submit(_gen_chunk, tag, eps): idx for idx, tag, eps in units}
            for fut, idx in list(futs.items()):
                results[idx] = fut.result()
    else:
        for idx, tag, eps in units:
            logger.info("  generating %d endpoint(s) for tag '%s'...", len(eps), tag)
            results[idx] = _gen_chunk(tag, eps)

    all_eps: list = []
    for idx in range(len(units)):             # deterministic order, regardless of concurrency
        all_eps.extend(results.get(idx, []))

    skeleton["endpoints"] = all_eps
    return skeleton


def _is_timeout(exc: Exception) -> bool:
    """True for SDK/HTTP timeout errors, without importing anthropic error types."""
    name = type(exc).__name__.lower()
    return "timeout" in name or "timeout" in str(exc).lower()


def design(facts: dict, decision: dict) -> dict:
    """Generate the contract. By default goes straight to the batched path
    (skeleton + per-tag), because a single-shot attempt almost always truncates
    for a real-sized API — wasting a slow call before the fallback takes over.
    Set API_CONTRACT_SINGLE_SHOT=1 to try one-shot first (small APIs only), in
    which case a truncation or timeout still falls back to batched."""
    if not SINGLE_SHOT:
        return _design_batched(facts, decision)
    user = _facts_and_choice(facts, decision) + "Produce the full API contract for the chosen approach."
    try:
        return _call_json(GENERATE_SYSTEM, user, max_tokens=CONTRACT_MAX_TOKENS)
    except TruncatedResponse:
        return _design_batched(facts, decision)
    except Exception as e:
        if _is_timeout(e):
            logger.info("Single-shot generation timed out; falling back to batched generation.")
            return _design_batched(facts, decision)
        raise


def generate_contract(inputs: dict) -> dict:
    facts = distill(inputs)
    logger.info("Deliberating on API-design approaches (model=%s)...", MODEL)
    decision = deliberate(facts)
    logger.info("Chosen approach: %s", decision.get("chosen"))
    logger.info("Generating API contract...")
    contract = design(facts, decision)
    # Guarantee a flat components map regardless of which shape the model returned
    # (single-shot or batched), so render/validate/$refs all resolve.
    contract["components"] = _normalize_components(contract.get("components"))
    n_ep = len(contract.get("endpoints", []))
    logger.info("Contract generated: %d endpoints, %d component schemas",
                n_ep, len(contract.get("components", {})))
    return {"decision": decision, "contract": contract, "facts": facts}


# ---------------------------------------------------------------------------
# Deterministic OpenAPI YAML rendering (no external yaml dependency)
# ---------------------------------------------------------------------------
def _inline(v) -> str:
    """Inline representation for scalars and EMPTY collections."""
    if isinstance(v, dict) and not v:
        return "{}"
    if isinstance(v, list) and not v:
        return "[]"
    return _yaml_scalar(v)


def _yaml_dump(value, indent: int = 0) -> list[str]:
    """Minimal, safe YAML emitter for JSON-like data (dict/list/scalar).
    Deterministic and dependency-free; quotes strings/keys that need it."""
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        if not value:
            return [f"{pad}{{}}"]
        for k, v in value.items():
            key = _yaml_key(k)
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{key}:")
                lines += _yaml_dump(v, indent + 1)
            else:
                lines.append(f"{pad}{key}: {_inline(v)}")
    elif isinstance(value, list):
        if not value:
            return [f"{pad}[]"]
        for item in value:
            if isinstance(item, (dict, list)) and item:
                block = _yaml_dump(item, indent + 1)
                first = block[0].lstrip()
                lines.append(f"{pad}- {first}")
                lines += block[1:]
            else:
                lines.append(f"{pad}- {_inline(item)}")
    else:
        lines.append(f"{pad}{_inline(value)}")
    return lines


def _yaml_key(k) -> str:
    k = str(k)
    # quote keys that would otherwise be misparsed (numbers, bools, null, specials)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_./{}\-]*", k) and \
            k.lower() not in ("true", "false", "null", "yes", "no", "on", "off"):
        return k
    return _quote(k)


def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # quote if it could be misparsed as non-string, or has special chars
    if s == "" or re.search(r'[:#\-?\[\]{}&*!|>%@`,\"\']', s) or s.strip() != s \
            or s.lower() in ("true", "false", "null", "yes", "no", "on", "off") \
            or re.fullmatch(r"[-+]?\d+(\.\d+)?", s):
        return _quote(s)
    return s


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _schema_or_ref(ref: str | None, schemas: set) -> dict:
    if ref and ref in schemas:
        return {"$ref": f"#/components/schemas/{ref}"}
    return {"type": "object"}


def _normalize_components(components) -> dict:
    """Return a FLAT schema-name -> definition map.

    The model sometimes returns the component block in OpenAPI's canonical
    nested shape — {"schemas": {Name: def, ...}} (optionally with a sibling
    "securitySchemes") — and sometimes as the flat {Name: def, ...} this agent's
    code expects. Left un-normalised, the canonical shape gets wrapped AGAIN by
    render_openapi into components.schemas.schemas.*, so no $ref resolves.
    Accept both: drop any securitySchemes (the renderer supplies its own) and, if
    all that remains is a single 'schemas' dict, unwrap it to the flat map."""
    if not isinstance(components, dict):
        return {}
    comp = dict(components)
    comp.pop("securitySchemes", None)              # renderer adds its own
    if set(comp.keys()) == {"schemas"} and isinstance(comp["schemas"], dict):
        return comp["schemas"]                     # unwrap canonical {schemas: {...}}
    return comp


_VALID_JSON_TYPES = {"string", "number", "integer", "boolean", "object", "array", "null"}


def _coerce_type(t: str):
    """Map a descriptive type string to a valid JSON-Schema (type, format).
    Models sometimes emit things like 'string (ISO8601 date)' or 'integer (cents)'."""
    low = t.lower()
    base = next((v for v in ("integer", "number", "boolean", "object", "array",
                             "null", "string") if v in low), "string")
    fmt = None
    if base == "string":
        if any(w in low for w in ("date-time", "datetime", "iso8601", "iso 8601", "timestamp")):
            fmt = "date-time"
        elif "date" in low:
            fmt = "date"
        elif "uuid" in low:
            fmt = "uuid"
        elif "email" in low:
            fmt = "email"
        elif "uri" in low or "url" in low:
            fmt = "uri"
    return base, fmt


def _sanitize_schema_types(node):
    """Recursively fix invalid JSON-Schema 'type' values in Schema Objects.
    Call ONLY on schema-bearing subtrees (components.schemas, paths) — never on
    securitySchemes, whose 'type' uses a different vocabulary (http/apiKey/...)."""
    if isinstance(node, dict):
        t = node.get("type")
        if isinstance(t, str) and t not in _VALID_JSON_TYPES:
            base, fmt = _coerce_type(t)
            node["type"] = base
            if fmt and "format" not in node:
                node["format"] = fmt
        for v in node.values():
            _sanitize_schema_types(v)
    elif isinstance(node, list):
        for v in node:
            _sanitize_schema_types(v)


def _normalize_refs(obj):
    """Rewrite $ref values to the canonical '#/components/schemas/<Name>'.
    Models often emit bare names ('Address') or a wrong path
    ('#/components/Address'); OpenAPI needs '#/components/schemas/Address'."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                name = v.rsplit("/", 1)[-1]          # last path segment
                out[k] = f"#/components/schemas/{name}"
            else:
                out[k] = _normalize_refs(v)
        return out
    if isinstance(obj, list):
        return [_normalize_refs(x) for x in obj]
    return obj


def render_openapi(contract: dict) -> str:
    info = contract.get("info", {"title": "API", "version": "1.0.0"})
    schemas = _normalize_refs(dict(contract.get("components", {})))
    schema_names = set(schemas.keys())

    sec_schemes = contract.get("security_schemes") or \
        {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}
    default_scheme = next(iter(sec_schemes))

    doc = {
        "openapi": "3.1.0",
        "info": info,
        "servers": [{"url": u} for u in contract.get("servers", ["/"])],
        "tags": contract.get("tags", []),
        "paths": {},
        "components": {"schemas": schemas, "securitySchemes": sec_schemes},
    }

    for ep in contract.get("endpoints", []):
        path = ep["path"]
        method = ep.get("method", "get").lower()
        op: dict = {}
        if ep.get("tag"):
            op["tags"] = [ep["tag"]]
        if ep.get("operationId"):
            op["operationId"] = ep["operationId"]
        if ep.get("summary"):
            op["summary"] = ep["summary"]
        if ep.get("roles"):
            op["description"] = f"Allowed roles: {', '.join(ep['roles'])}."

        params = []
        for p in ep.get("path_params", []):
            params.append({"name": p["name"], "in": "path", "required": True,
                           "schema": {"type": p.get("type", "string")},
                           **({"description": p["description"]} if p.get("description") else {})})
        for p in ep.get("query_params", []):
            params.append({"name": p["name"], "in": "query",
                           "required": bool(p.get("required", False)),
                           "schema": {"type": p.get("type", "string")},
                           **({"description": p["description"]} if p.get("description") else {})})
        if params:
            op["parameters"] = params

        req = ep.get("request")
        if req and method in ("post", "put", "patch"):
            content = {"schema": _schema_or_ref(req.get("schema_ref"), schema_names)}
            if "example" in req:
                content["example"] = req["example"]
            op["requestBody"] = {"required": True,
                                 "content": {"application/json": content}}

        responses: dict = {}
        for r in (ep.get("responses") or []):
            content = {"schema": _schema_or_ref(r.get("schema_ref"), schema_names)}
            if "example" in r:
                content["example"] = r["example"]
            responses[str(r.get("status", "200"))] = {
                "description": r.get("description", ""),
                "content": {"application/json": content},
            }
        op["responses"] = responses or {"200": {"description": "OK"}}

        if ep.get("security"):
            op["security"] = [{default_scheme: []}]
        else:
            op["security"] = []

        doc["paths"].setdefault(path, {})[method] = op

    # Deterministically coerce any invalid JSON-Schema 'type' the model may have
    # written (e.g. "string (ISO8601 date)") into a valid type + format, so the
    # emitted document is always spec-valid. Applied to schema-bearing subtrees
    # only — never to securitySchemes, whose 'type' vocabulary differs.
    _sanitize_schema_types(doc["components"]["schemas"])
    _sanitize_schema_types(doc["paths"])

    return "\n".join(_yaml_dump(doc)) + "\n"


def build_sample_payloads(contract: dict) -> dict:
    """Companion sample-payloads.json: named request/response examples per operation."""
    samples = {}
    for ep in contract.get("endpoints", []):
        op_id = ep.get("operationId") or f"{ep.get('method','get')}_{ep['path']}"
        entry = {"method": ep.get("method", "get").upper(), "path": ep["path"]}
        if (ep.get("request") or {}).get("example") is not None:
            entry["request"] = ep["request"]["example"]
        resp_examples = {str(r.get("status")): r["example"]
                         for r in (ep.get("responses") or []) if "example" in r}
        if resp_examples:
            entry["responses"] = resp_examples
        if "request" in entry or "responses" in entry:
            samples[op_id] = entry
    return samples


# ---------------------------------------------------------------------------
# Light deterministic self-validation (warnings only)
# ---------------------------------------------------------------------------
def validate_contract(contract: dict, facts: dict) -> list[str]:
    warnings: list[str] = []
    schema_names = set(contract.get("components", {}).keys())
    endpoints = contract.get("endpoints", [])
    if not endpoints:
        warnings.append("contract has no endpoints")

    def norm(s):
        return re.sub(r"[^a-z]", "", str(s).lower())

    # every referenced schema must be defined
    for ep in endpoints:
        for ref in ([(ep.get("request") or {}).get("schema_ref")] +
                    [r.get("schema_ref") for r in (ep.get("responses") or [])]):
            if ref and ref not in schema_names:
                warnings.append(f"{ep.get('method','?').upper()} {ep.get('path','?')} "
                                f"references undefined schema '{ref}'")
        # error shape present on mutating ops?
        if ep.get("method", "get").lower() in ("post", "put", "patch", "delete"):
            statuses = {str(r.get("status")) for r in (ep.get("responses") or [])}
            if not any(s.startswith(("4", "5")) for s in statuses):
                warnings.append(f"{ep.get('method').upper()} {ep.get('path')} has no error response")

    # every resource covered by at least one endpoint?
    paths_blob = " ".join(norm(ep.get("path", "")) for ep in endpoints)
    for res in facts.get("resources", []):
        r = norm(res)
        if r and r not in paths_blob and r.rstrip("s") not in paths_blob \
                and (r[:-1] + "ies" if r.endswith("y") else r + "s") not in paths_blob:
            warnings.append(f"resource '{res}' has no obvious endpoint")

    # protected operations should reference known roles (from user_features labels
    # OR the schema's declared role enum — the contract legitimately uses either)
    roles = {norm(r) for r in facts.get("roles", []) if r} \
        | {norm(r) for r in facts.get("role_values", []) if r}
    for ep in endpoints:
        for role in ep.get("roles", []):
            if roles and norm(role) not in roles:
                warnings.append(f"{ep.get('method','?').upper()} {ep.get('path','?')} "
                                f"references unknown role '{role}'")
    return warnings


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def render_decision_md(decision: dict, contract: dict) -> str:
    lines = ["# API Contract — Design Decision\n"]
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
    eps = contract.get("endpoints", [])
    lines.append(f"\n## Endpoints ({len(eps)})")
    for ep in eps:
        sec = "🔒" if ep.get("security") else "🌐"
        roles = f" [{', '.join(ep['roles'])}]" if ep.get("roles") else ""
        lines.append(f"- {sec} `{ep.get('method','get').upper()} {ep.get('path','')}` — "
                     f"{ep.get('summary','')}{roles}")
    return "\n".join(lines)


def write_outputs(shared: Path, result: dict) -> dict:
    contract = result["contract"]
    paths = {
        "yaml": shared / OUT_YAML,
        "samples": shared / OUT_SAMPLES,
        "decision": shared / OUT_DECISION,
    }
    paths["yaml"].write_text(render_openapi(contract), encoding="utf-8")
    paths["samples"].write_text(
        json.dumps(build_sample_payloads(contract), indent=2, ensure_ascii=False), encoding="utf-8")
    paths["decision"].write_text(
        render_decision_md(result["decision"], contract), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}


# ---------------------------------------------------------------------------
# Reusable core + entrypoints
# ---------------------------------------------------------------------------
def run(shared_dir: str | None = None, inputs: dict | None = None) -> dict:
    load_dotenv_files()
    shared = resolve_shared_dir(shared_dir)
    if inputs is None:
        inputs = load_inputs(shared)
    result = generate_contract(inputs)
    result["warnings"] = validate_contract(result["contract"], result["facts"])
    result["paths"] = write_outputs(shared, result)
    return result


def api_contract_node(state: dict) -> dict:
    """LangGraph node. Reads `shared_dir` (and optional preloaded `inputs`) from
    state; returns the API contract to merge back into state."""
    shared_dir = state.get("shared_dir") or state.get("SHARED_DIR")
    inputs = state.get("inputs")
    result = run(shared_dir=shared_dir, inputs=inputs)
    return {
        "api_contract": result["contract"],
        "api_contract_decision": result["decision"],
        "api_contract_paths": result["paths"],
        "api_contract_warnings": result["warnings"],
    }


def main():
    ap = argparse.ArgumentParser(description="Generate the API contract (OpenAPI + samples) from the earlier artifacts")
    ap.add_argument("--dir", default=None, help=f"shared folder (inputs in, outputs out). Overrides ${ENV_VAR}.")
    args = ap.parse_args()

    try:
        result = run(shared_dir=args.dir)
    except TruncatedResponse:
        raise SystemExit(
            "The model's response was cut off (hit the token ceiling) and the "
            "contract could not be assembled, so no files were written.\n"
            "Fixes: raise the budget with API_CONTRACT_MAX_TOKENS (e.g. 24000), "
            "or split the app into more, smaller resource groups. The batched "
            "fallback also retries the skeleton at a larger budget automatically."
        )
    contract = result["contract"]
    print(f"Chosen approach: {result['decision'].get('chosen')}")
    print(f"Endpoints: {len(contract.get('endpoints', []))}  ·  "
          f"Schemas: {len(contract.get('components', {}))}")
    print(f"openapi.yaml -> {result['paths']['yaml']}")
    print(f"sample-payloads.json -> {result['paths']['samples']}")
    for w in result["warnings"]:
        print(f"  ⚠ {w}")


if __name__ == "__main__":
    main()