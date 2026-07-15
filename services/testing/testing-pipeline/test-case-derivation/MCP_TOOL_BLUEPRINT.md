# MCP Tool Blueprint — Test-Case Generation Tool (for Module B / Stage B)

> **Purpose:** rebuild the ZenseAI MCP test-case tool as a working look-alike inside this
> testing agent, so Stage B's `mcp_adapter.py` has a real MCP tool to call (instead of the
> current inert stub → direct-LLM fallback).
>
> **Scope of this doc:** blueprint/spec only. No implementation is written here. Everything
> is traced to real files in `zenseai-hub-refined/` with paths + line numbers.

---

## 1. Overview

ZenseAI ships a single **FastMCP** server (`mcp_servers/server.py`) that exposes ~40 tools.
Each tool is a **thin proxy**: it forwards a text `user_input` to a remote "aibuddy" agent
platform (`http://10.0.0.4`), polls until the job completes, and returns the produced files.
The tool relevant to our Stage B is **`call_python_test_case_generation_genie`** (aibuddy
agent id `PYTHON_TEST_GENIE = 245778`), the "Python Test Case Generation Genie."

For our Module B we recreate the **MCP mechanics** (a FastMCP server exposing a
test-case-generation tool over HTTP) but **replace the aibuddy backend** — which we don't
have — with our **own LLM-backed derivation** (the same logic as `direct_planner.py`). The
result is a standalone MCP tool our `derivation_router.py` can prefer when available, with
the direct-LLM planner remaining the permanent fallback (reference §5).

> ⚠️ **Important semantic note.** The ZenseAI genie emits pytest **test code**
> (`{"tests":[{"path","content"}]}`) — that is closer to our **Stage C** (test-code
> generation) than Stage B's `{id, req_id, input, expected}` cases. Our recreated tool is
> **adapted** to emit Stage B's `test_cases` schema. See §9 Open Questions.

---

## 2. Source Reference (zenseAi files)

All paths under `zenseai-hub-refined/`.

| Path | Role |
|---|---|
| `mcp_servers/server.py` | The FastMCP server. `mcp = FastMCP(...)` (line 7); `_execute_agent` proxy helper (line 141); **`call_python_test_case_generation_genie`** tool (decorator line 373, fn line 390); `extract_file_contents` (line 11); `if __name__ == "__main__": mcp.run()` (end of file). |
| `mcp_servers/constants.py` | `BASE_URL = "http://10.0.0.4/api/aibuddy/executeAgent"` (line 1); agent ids incl. `PYTHON_TEST_GENIE = "245778"`. |
| `mcp_servers/helpers.py` | Mongo/LLM/decrypt helpers (`get_api_dict`, `initialize_llm`, `get_dependency_graph_mongodb`, `decrypt`, mermaid gens). **Not used by the test-case tool** — used by other tools (e.g. `dependency_diagram_mongodb`). |
| `mcp_servers/database.py` | SQLAlchemy MySQL engine (hardcoded `zenseai_main`). **Not used by the test-case tool.** |
| `mcp_servers/requirements.txt` | Deps: `fastmcp==2.12.4`, langchain stack, boto3, pymongo, etc. Only `fastmcp` + `httpx` matter for the test tool. |
| `mcp_servers/Dockerfile` | Run command: `fastmcp run server.py:mcp --transport http --host 0.0.0.0 --port 10000`. |
| `mcp_servers/__init__.py`, `.gitignore` | Package marker / venv ignore. |
| `multi-agent-system/src/api/routers/mcp_server.py` | **Different subsystem** — an SSE MCP surface for the `mas` workflow engine (`/mcp/sse`), *not* a client of `mcp_servers/server.py`. Cited for completeness. |
| `multi-agent-system/src/service/mcp_client.py` | Client for the `mas` workflow API (`/mas/v1/execute` → poll). Also *not* a client of the FastMCP tool server. |

> **No in-repo client calls `mcp_servers/server.py` directly.** It is invoked by a standard
> MCP client over its HTTP transport (see §5).

---

## 3. Architecture

### 3.1 ZenseAI (as-is)

```
MCP client ──(MCP over HTTP :10000)──► FastMCP server (server.py, "ZenseAI-Agent-Executer")
                                          │  tool: call_python_test_case_generation_genie
                                          ▼
                                   _execute_agent(URL, token, api_id, user_input)
                                          │  1. write user_input -> temp .txt
                                          │  2. POST multipart to
                                          │     http://10.0.0.4/.../executeAgent/245778
                                          │  3. poll .../getStaticAgentInfo/{job_id}
                                          │     every 10s, up to 60 tries, until COMPLETED
                                          ▼
                                   {stepInformation, fileContents{...}}
```

### 3.2 Recreated for Module B (target)

```
Stage B derivation_router ──► mcp_adapter ──(MCP client over HTTP)──► OUR FastMCP server
   (prefers MCP if healthy)                                              │ tool: generate_test_cases
                                                                         ▼
                                                        local backend = LLM (TESTING_LLM_*)
                                                        (same prompt as direct_planner.py)
                                                                         ▼
                                                        {schema_version, test_cases:[...]}   ← Stage B schema
```

The aibuddy POST-and-poll hop is replaced by one direct LLM call. Everything else (a FastMCP
server, one registered tool, HTTP transport) is preserved.

---

## 4. Exact Interfaces

### 4.1 ZenseAI tool — registration (server.py:373–398, verbatim shape)

```python
mcp = FastMCP("ZenseAI-Agent-Executer")                     # server.py:7

@mcp.tool(
    title="Python Test Case Generation Genie",
    description="""...generates comprehensive pytest test suites for FastAPI ...
        strict output contract returning only JSON {"tests":[{"path":"...","content":"..."}]} ...""",
    annotations={"env": "ZenseAI", "projectID": 246900, "projectName": "MCP"},
)
async def call_python_test_case_generation_genie(
    user_input: str, bearer_token: str, api_id: int
) -> dict:
    URL = BASE_URL + "/" + PYTHON_TEST_GENIE          # http://10.0.0.4/.../executeAgent/245778
    if not bearer_token.startswith("Bearer "):
        bearer_token = "Bearer " + bearer_token
    return await _execute_agent(URL, bearer_token, api_id, user_input)
```

- **Tool name** (what a client calls): the function name `call_python_test_case_generation_genie`
  (FastMCP registers by function name; `title` is display-only).
- **Inputs:** `user_input: str` (a JSON description of FastAPI routes, optionally coverage.xml),
  `bearer_token: str` (aibuddy auth), `api_id: int` (aibuddy LLM-credential selector).
- **Return (tool):** `{ "stepInformation": {...}, "fileContents": { "<step>": "<combined text>" } }`
  (`_execute_agent` → `extract_file_contents`, server.py:11, 226–235). The genie's own
  `{"tests":[...]}` payload arrives *inside* `fileContents`.

### 4.2 `_execute_agent` proxy contract (server.py:141–240)

- POST `multipart/form-data` to `BASE_URL/<agent_id>`: fields `fileNames`, `userQuery=""`,
  `workspaceUuid` (hardcoded `ed363338-...`, server.py:9), `workSpaceDirPath=""`, `apiId`;
  header `Authorization: <bearer_token>`; file part `files=(<name>, <user_input bytes>)`.
- Parse a job id from the POST response (`id|jobId|taskId|result|uuid`).
- Poll `GET http://10.0.0.4/api/aibuddy/getStaticAgentInfo/{job_id}` (server.py:204) every
  10 s, `max_attempts = 60`, until `overAllStatus == "COMPLETED"`.
- Timeouts: POST `httpx.Timeout(300, connect=60)`; poll `httpx.Timeout(120, connect=60)`.
- Errors returned as dicts: `{"error": "empty_response"|"poll_failed"|"timeout_waiting_for_completion", ...}`.

### 4.3 Recreated tool — target interface (Module B native)

```python
from fastmcp import FastMCP
mcp = FastMCP("testing-testcase-tool")

@mcp.tool(
    title="Test Case Derivation",
    description="Derive concrete test cases (id, req_id, type, input, expected) per "
                "requirement from requirements + mapping tree + strategy.",
)
async def generate_test_cases(
    requirements: list[dict],
    mapping_tree: dict,
    strategy: dict,
) -> dict:
    """Returns the Stage B test_cases artifact:
       { "schema_version": "1.0",
         "test_cases": [ {"id","req_id","type","input","expected","notes","target_symbols"} ] }
    """
    ...
```

- **Output must validate against** `contracts/test_cases.schema.json` (already in this folder),
  so `mcp_adapter.normalize_response` becomes near-identity.
- Auth (optional, POC): a static token via `TESTING_MCP_API_KEY`, checked by the server —
  *not* aibuddy's `bearer_token`/`api_id`.

---

## 5. Dependencies & Setup

### 5.1 Packages (for the recreated tool only)

| Package | Version | Why |
|---|---|---|
| `fastmcp` | `2.12.4` (match zenseAi, `mcp_servers/requirements.txt`) | MCP server + client |
| `httpx` | already pinned in `services/testing/requirements.txt` | transport / health |
| `litellm` | already pinned (Stage B) | the LLM backend replacing aibuddy |
| `pydantic` | already pinned | validate against `test_cases.schema.json` |

Drop everything else in `mcp_servers/requirements.txt` (langchain, boto3, pymongo,
sqlalchemy, mysql-connector, google-generativeai, pycryptodome) — none are needed for the
test-case tool.

### 5.2 Env vars (placeholders only; add to root `.env.example`)

Reuse what Stage B already defines (`tcd_config.py`):

| Var | Purpose |
|---|---|
| `TESTING_MCP_URL` | MCP server URL the adapter connects to (e.g. `http://localhost:10001/mcp`). Unset ⇒ router uses direct-LLM. |
| `TESTING_MCP_API_KEY` | optional static auth token the server checks. |
| `TESTING_MCP_TIMEOUT` | client timeout seconds. |
| `TESTING_LLM_MODEL` / `_API_KEY` / `_BASE_URL` | the LLM the tool's backend calls (shared with Stage A/B). |

### 5.3 What goes where

- New standalone server dir (see §6) with its own `requirements.txt` + `Dockerfile`.
- `mcp_adapter.py` (this folder) updated to speak the MCP protocol (see §7).

---

## 6. Recreation Steps (file-by-file, matched to our conventions)

Create a **standalone MCP server** (the reference treats the ZenseAI tool as an *external,
additive* dependency — keep it out-of-process, mirroring `mcp_servers/`). Suggested location,
consistent with v1's service layout:

```
services/testing/mcp-servers/testcase-tool/
├── server.py            # FastMCP server; registers generate_test_cases
├── backend.py           # LLM-backed derivation (port direct_planner's prompt + parsing)
├── config.py            # LLM + auth settings (env: TESTING_LLM_*, TESTING_MCP_API_KEY)
├── requirements.txt     # fastmcp==2.12.4, httpx, litellm, pydantic
├── Dockerfile           # fastmcp run server.py:mcp --transport http --host 0.0.0.0 --port 10001
└── README.md
```

Order:

1. **`config.py`** — LLM settings (reuse `TESTING_LLM_` prefix so one `.env` serves all) +
   optional `TESTING_MCP_API_KEY`.
2. **`backend.py`** — the real work: build the derivation prompt (port `direct_planner.py`'s
   `_SYSTEM_INSTRUCTIONS` + `_build_messages`), call the LLM (port `tcd_llm_client.py`), parse
   with the same tolerant logic (port `test_case_models.parse_test_cases`). Output = the
   Stage B `test_cases` list. *(Standalone service ⇒ it can't import the in-process Stage B
   modules; copy the ~3 small pieces or, later, share via `packages/`.)*
3. **`server.py`** — `mcp = FastMCP("testing-testcase-tool")`; one `@mcp.tool` →
   `generate_test_cases(requirements, mapping_tree, strategy)` calling `backend.py`; optional
   token check; `if __name__ == "__main__": mcp.run()` (mirrors zenseAi server.py end).
4. **`requirements.txt`, `Dockerfile`** — mirror `mcp_servers/` but trimmed (§5.1); HTTP
   transport on a free port (e.g. 10001).
5. **`README.md`** — how to run + call.
6. **Update `mcp_adapter.py`** (this folder) — see §7.

---

## 7. zenseAi-Specific Adaptations (swap/stub each)

| zenseAi coupling (file:loc) | Replacement in our recreation |
|---|---|
| `BASE_URL = http://10.0.0.4/...` (constants.py:1) — aibuddy platform | Our LLM via `litellm` (`TESTING_LLM_*`). No aibuddy. |
| `_execute_agent` upload+poll (server.py:141) | One direct LLM call in `backend.py`. |
| Agent ids incl. `PYTHON_TEST_GENIE=245778` (constants.py) | N/A — no remote agents. |
| `bearer_token` + `api_id` params (aibuddy auth/credential selector) | Drop from the tool signature. Optional static `TESTING_MCP_API_KEY` for server auth. |
| `workspaceId` hardcoded (server.py:9) | N/A. |
| `helpers.py` (mongo, `get_api_dict`, `initialize_llm`, `decrypt`) | Not used by the test tool — omit entirely. |
| `database.py` MySQL engine | Not used by the test tool — omit. |
| Output `{stepInformation, fileContents}` (aibuddy shape) | Our `{schema_version, test_cases:[...]}` (Stage B schema). |
| **Client transport mismatch** — our `mcp_adapter.py` currently assumes REST `GET /health` + `POST /generate`; FastMCP speaks **MCP JSON-RPC over HTTP**, not plain REST. | Update `mcp_adapter` to use a **`fastmcp.Client`**: `health()` = connect + `list_tools()`; `generate_test_cases()` = `client.call_tool("generate_test_cases", {...})`; `normalize_response()` unwraps the tool result → `test_cases`. |

---

## 8. Verification

1. **Unit (backend, no server):** call `backend.generate(...)` with an injected fake LLM →
   assert it returns a list validating against `contracts/test_cases.schema.json`.
2. **Server up:** `python server.py` (stdio) or `fastmcp run server.py:mcp --transport http
   --port 10001`. A `fastmcp.Client` should list one tool: `generate_test_cases`.
3. **Round-trip via the adapter:** set `TESTING_MCP_URL=http://localhost:10001/mcp`, run Stage B
   (`run_stage.py`). Expect `derivation_router` to report **`source: "mcp"`** (not
   `direct_llm`), with the same `requirements_coverage` / grounding as the direct path.
4. **Fallback still works:** stop the server → Stage B logs an MCP failure and returns
   `source: "direct_llm"`. (This is the reference §5 guarantee.)

A successful MCP call returns, e.g.:
```json
{ "schema_version": "1.0",
  "test_cases": [ {"id":"TC-003-1","req_id":"REQ-003","type":"boundary",
                   "input":{"age":120},"expected":{"raises":false}} ] }
```

---

## 9. Open Questions / Risks

1. **Genie output ≠ Stage B artifact.** The real ZenseAI genie returns pytest **code**
   (`{"tests":[{path,content}]}`) — Stage C territory — not `{id,req_id,input,expected}`
   cases. **Decision needed:** recreate a *Stage-B-native* tool (emit cases; recommended, done
   above) vs. a faithful *code-emitting* tool better suited to Stage C. *(Assumption in this
   blueprint: Stage-B-native.)*
2. **Transport/protocol.** FastMCP HTTP is MCP JSON-RPC, not REST. The current
   `mcp_adapter.py` stub assumes REST `/health` + `/generate`; it must move to a
   `fastmcp.Client` (§7). Alternatively, expose a thin REST shim — decide which.
3. **In-process vs. out-of-process.** Reference §5 models MCP as external/additive, so a
   separate server is the faithful choice; but for the POC an in-process function would be
   simpler. Running a real MCP server adds a process to manage. *(Blueprint assumes external,
   matching zenseAi.)*
4. **Code duplication.** A standalone server can't import the in-process Stage B modules, so
   the prompt/LLM/parser get copied. Plan to consolidate into `packages/` later (already noted
   in Stage B's README).
5. **fastmcp version drift.** zenseAi pins `fastmcp==2.12.4`; the `Client`/`@mcp.tool` API
   should be pinned to the same to avoid surprises.
6. **Auth model.** zenseAi's `bearer_token`/`api_id` are aibuddy-platform concepts with no
   analog here. Confirm whether any auth is needed for the local tool (POC: optional static
   token).
7. **No reference client.** The repo has no client that calls `mcp_servers/server.py`
   directly (the `mas` `mcp_client.py`/`mcp_server.py` target a different subsystem), so the
   client-side handshake for *this* server is inferred from standard FastMCP usage, not copied.
```
