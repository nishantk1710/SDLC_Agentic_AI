# Access Needed — ZenseAI MCP Test-Case Tool (Testing Phase, Stage B)

We've built our Testing agent's Stage B (test-case derivation) to call the ZenseAI
**Python Test Case Generation Genie** MCP tool, with a local LLM fallback until we
have access. To switch on the **real** tool we need the items below.

Our adapter: `services/testing/testing-pipeline/test-case-derivation/mcp_adapter.py`
(connects with a `fastmcp` client). Everything here maps to config in our
`v1/.env.example` (`TESTING_MCP_*`).

References (your repo, `zenseai-hub-refined/`): `mcp_servers/server.py`
(the FastMCP server + tool `call_python_test_case_generation_genie`, ~line 390),
`mcp_servers/constants.py` (`PYTHON_TEST_GENIE = 245778`, `BASE_URL`),
`mcp_servers/Dockerfile` (run command), `mcp_servers/requirements.txt`
(`fastmcp==2.12.4`).

---

## 1. What we need (please provide)

| # | Item | Maps to our env var | Notes / why |
|---|---|---|---|
| 1 | **MCP server URL** of the deployed tool (host + port + path), e.g. `https://<host>:10000/mcp` | `TESTING_MCP_URL` | Your `Dockerfile` runs `fastmcp run server.py:mcp --transport http --host 0.0.0.0 --port 10000`. We need the externally reachable URL + the exact HTTP path (`/mcp`? `/sse`?). |
| 2 | **Tool name** to call | `TESTING_MCP_TOOL_NAME` | We default to `call_python_test_case_generation_genie`. Confirm it's unchanged in your deployment. |
| 3 | **`bearer_token`** value (or how to obtain one) + its lifetime/refresh | `TESTING_MCP_API_KEY` | The tool takes `bearer_token` and sends it as `Authorization` to the aibuddy platform. How do we mint/rotate it? |
| 4 | **`api_id`** to use | `TESTING_MCP_API_ID` | The tool's `api_id` arg (aibuddy credential/model selector). Which value should we pass? |
| 5 | **Transport auth** (if any) on the MCP server itself | (new, TBD) | Does the FastMCP HTTP endpoint require its own header/API key, separate from the tool's `bearer_token` arg? If so, name + how to obtain. |
| 6 | **Network reachability** confirmation | — | The tool internally calls `http://10.0.0.4/api/aibuddy/executeAgent/245778` and `.../getStaticAgentInfo/{job_id}` (`constants.py`, `server.py`). Is `10.0.0.4` reachable from where the MCP server runs, and is the MCP server reachable from our network (VPN/allowlist)? |
| 7 | **SDK version** confirmation | — | We pin `fastmcp==2.12.4` (your `requirements.txt`) so client/server match. Confirm the deployed server's version. |

---

## 2. Open questions (needed before we finalize)

1. **Input format for `user_input`.** The tool's description says it accepts "JSON
   descriptions of FastAPI routes and optionally coverage.xml." We currently send a
   JSON string `{instruction, requirements, symbols, strategy}`. **What is the exact
   expected `user_input` schema/shape?** (A sample request would be ideal.)
2. **Output shape confirmation.** We parse the tool's return `{stepInformation,
   fileContents{...}}` and look inside `fileContents` for the genie's
   `{"tests":[{"path","content"}]}` payload. **Which `fileContents` step/key holds
   the tests JSON**, and is the `{"tests":[...]}` contract stable? (A sample response
   would let us finalize normalization.)
3. **Requirement traceability.** The genie returns test **code files**, not per-
   requirement cases. Is there any way to get the tool to tag output by requirement
   id, or must we treat its output as untraced (our current assumption)?
4. **Latency / polling / limits.** The tool polls aibuddy up to 60 × 10 s (~10 min).
   What is the realistic completion time, and are there rate limits or concurrency
   caps we should respect?
5. **Non-Python stacks.** This genie is Python-only. Are there equivalent MCP tools
   for Node/JS-TS/Java (agent ids)? If so, we can register them as additional
   handlers; otherwise those stacks stay on our LLM fallback.
6. **Environment/isolation.** Any restriction on what source code we may send (data
   residency / confidentiality), given the tool forwards our input to the aibuddy
   platform?

---

## 3. How we'll use it (for your context)

- Stage B calls the tool **only for Python stacks**, and **only when configured +
  healthy**; every other stack and any failure falls back to our own LLM planner —
  so granting access is additive and low-risk on your side.
- We connect via a standard `fastmcp` client: `list_tools()` for a health check,
  then `call_tool("<tool>", {user_input, bearer_token, api_id})`.
- Nothing is sent until we set `TESTING_MCP_URL`; today it is unset (fallback only).

---

## 4. Assumptions we've made (please correct if wrong)

- The deployed tool is the FastMCP server in `mcp_servers/server.py`, HTTP transport,
  tool `call_python_test_case_generation_genie` (agent `245778`).
- Auth is via the tool's `bearer_token` + `api_id` args (no separate transport key) —
  **unconfirmed** (see item 5 above).
- The `{"tests":[{"path","content"}]}` output contract is stable — **unconfirmed**
  (see open question 2).
