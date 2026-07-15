# Stage A — Interface Extraction

The first pipeline stage after source loading. Turns loaded source code +
requirements into a test **strategy**:

```
A1  chunker            source files            -> chunks[]        (Python=ast, JS/TS=tree-sitter)
A2  mapping_tree        chunks[]                -> mapping tree     (call/dependency graph)
A3  strategy_planner    mapping tree + reqs     -> test_strategy    (LLM; grounded + coverage-checked)
```

## How it plugs into the Testing Phase

- Invoked by `services/testing/main.py` as **Stage A** via
  `run_interface_extraction()` (imported the same flat-module / `sys.path` way as
  the Source Loader Service). Module names here are unique so they don't collide
  with the source-loader's modules on `sys.path`.
- **Inputs** (produced by the Source Loader Service, read by `inputs.py`):
  - `data/input/unzipped-code/` → source files (A1)
  - `data/input/SRS/` → requirements (A3). *POC shim:* the first JSON file found
    is read as the requirements list; swap for the frozen SRS parser later.
- **Outputs** (written to `data/`):
  - `data/Chunks/chunks.json` (A1)
  - `data/mapping-tree.json` (A2)
  - `data/test-strategy.json` (A3)

## Files

| File | Role |
|---|---|
| `chunker.py` | A1 — symbol-level chunks; parser registry (Python `ast`, JS/TS tree-sitter) |
| `tree_sitter_parsers.py` | A1 — JS/TS extraction (offline grammars) |
| `fallback_chunker.py` | A1 — coarse splitter for languages without a parser |
| `mapping_tree.py` | A2 — call graph with `calls`/`called_by`/`fan_in`/`fan_out` |
| `strategy_planner.py` | A3 — LLM strategy + F1 grounding, F2 coverage, F3 fan-in, F4 technique hints |
| `llm_client.py` | LiteLLM wrapper (lazy import); env config via `TESTING_LLM_*` |
| `ie_config.py` | paths + LLM settings |
| `inputs.py` | adapts source-loader output → A1/A3 inputs |
| `interface_extraction.py` | stage orchestrator (`run_interface_extraction`) |
| `run_stage.py` | standalone CLI (`--mock` for offline) |
| `contracts/` | JSON Schemas for the mapping-tree and test-strategy artifacts |

## Run standalone

```bash
# from this directory
python run_stage.py --mock     # offline (canned A3), no API key
python run_stage.py            # real A3 (needs TESTING_LLM_API_KEY in .env)
```

A3 needs an LLM; without one it degrades to a valid-but-empty strategy so the
pipeline never breaks. LLM config comes from `TESTING_LLM_*` env vars (see root
`.env.example`); the verified Azure-Anthropic routing is
`anthropic/<model>` + `TESTING_LLM_BASE_URL=https://<res>.services.ai.azure.com/anthropic/`.

## Tests

```bash
pytest tests -q
# or without pytest:
python tests/test_interface_extraction.py
```
