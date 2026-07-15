# Stage B — Test-Case Derivation

Turns Stage A's **strategy** (what/where to test) into concrete **test cases**
(inputs + expected results) per requirement — the auditable artifact the code
generator (Stage C) consumes.

```
requirements + mapping tree + strategy
        -> router (ZenseAI MCP if healthy, else direct-LLM fallback)
        -> ground + complete
        -> data/test-cases.json
```

## MCP vs. direct-LLM (reference §5)

The router prefers the **ZenseAI MCP** test-case tool when it is available and
healthy, and otherwise uses the **direct-LLM planner** — both return the same
schema. The direct-LLM path is the primary, permanently-available path; MCP is
**additive, never a hard dependency**.

> **POC status:** no MCP access yet, so `mcp_adapter` is inert
> (`is_available()` is False unless `TESTING_MCP_URL` is set) and the router
> always uses the direct-LLM planner. To wire MCP later: set `TESTING_MCP_URL`
> (+ `TESTING_MCP_API_KEY`), implement the HTTP call in
> `mcp_adapter.generate_test_cases`, and complete the field mapping in
> `mcp_adapter.normalize_response`. Nothing else in Stage B changes.

## Trust rules (reference §7)

- **Expected-from-requirements** — `expected` values are derived only from the
  requirements / acceptance criteria; the mapping tree is used solely for the
  `input` call shape. Enforced in the planner prompt.
- **Completeness** — every requirement must have ≥ 1 case; otherwise it is
  reported under `requirements_coverage.uncovered` (drives a non-PASS verdict
  later).
- **Grounding** — `target_symbols` not present in the mapping tree are dropped
  and recorded; cases with an unknown `req_id` are flagged.
- **Case types** — `happy_path`, `boundary`, `invalid_input`, `error_handling`.

## Files

| File | Role |
|---|---|
| `direct_planner.py` | Direct-LLM planner (primary path / permanent fallback) |
| `mcp_adapter.py` | ZenseAI MCP seam (inert until access) + response normalizer |
| `derivation_router.py` | cache → MCP-if-healthy → direct-LLM |
| `tcd_cache.py` | content-addressed cache of derived cases (reference §7.5) |
| `test_case_models.py` | Pydantic models + tolerant parsing of LLM/MCP output |
| `test_case_derivation.py` | orchestrator (`run_test_case_derivation`) |
| `tcd_config.py` | paths + LLM (`TESTING_LLM_`) + MCP (`TESTING_MCP_`) settings |
| `tcd_llm_client.py` | LiteLLM wrapper (lazy import) |
| `run_stage.py` | standalone CLI (`--mock`, `--no-cache`) |
| `contracts/test_cases.schema.json` | output schema |

## Inputs / outputs

- **Inputs** (Stage A artifacts in `data/`): `requirements.json`,
  `mapping-tree.json`, `test-strategy.json`.
- **Output**: `data/test-cases.json`.

## Run standalone

```bash
# from this directory (Stage A must have produced its artifacts first)
python run_stage.py --mock     # offline
python run_stage.py            # real LLM (needs TESTING_LLM_API_KEY)
```

## Tests

```bash
python tests/test_test_case_derivation.py   # or: pytest tests -q
```

> FUTURE: `tcd_llm_client.py` duplicates Stage A's LLM client to keep stages
> self-contained on the shared `sys.path`; consolidate both into a shared
> `packages/llm` module once `packages/` is fleshed out.
