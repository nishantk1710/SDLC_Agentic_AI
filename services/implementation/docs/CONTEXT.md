# SDLC Multi-Agent System — Development Context & Contracts

> **Purpose:** the single source of truth for building the POC **in parallel**.
> It locks down the *contracts* (shared state, agent interfaces, folder layout,
> tool wrappers) so multiple developers can build different agents at the same
> time without breaking each other.
>
> Companion doc: [`AGENTS.md`](./AGENTS.md) — detailed responsibilities & flows.
> This doc = **how we build it together**.

---

## 0. Confirmed Agents & Tools (locked)

| # | Agent | Core Tools (keep) | Optional / Later | LLM |
|---|-------|-------------------|------------------|-----|
| 1 | Code Generation | LangGraph, LLM, GitPython, Jinja2 | — | ✅ |
| 2 | Code Review | LLM, Ruff (Python), ESLint (React/TS) | Tree-sitter (custom rules only) | ✅ |
| 3 | Refactoring | LLM, Black (Python), Prettier (React/TS) | Tree-sitter (custom rules only) | ✅ |
| 4 | Debugging | LLM, Python subprocess | Docker (add when isolation needed) | ✅ |
| 5 | Unit Test Generator | LLM, pytest (Python), Jest (React) | — | ✅ |
| 6 | Documentation | LLM | FastAPI OpenAPI (only if app is FastAPI) | ✅ |
| 7 | Security | Semgrep, pip-audit, npm audit | LLM (plain-English summaries) | ⚠️ Optional |

*All tools open source. Only paid part = LLM API (use Ollama for 100% free).*

---

## 1. The Golden Rule for Parallel Work

**Every agent is a pure function of the shared state:**

```python
def run(state: State) -> State:
    ...
    return state
```

- It **reads** the keys it needs, **writes** the keys it owns, and **returns** the
  updated state.
- It must **not** rename or delete keys owned by other agents.
- As long as everyone honors the [State Contract](#3-the-state-contract) and the
  [Agent Interface Contract](#4-agent-interface-contract), all 7 agents can be
  built, tested, and merged **independently**.

Each developer can build their agent against a **mock state** without waiting for
upstream agents to be finished.

---

## 2. Repository Layout

```
c:\ISG\SDLC\
├── docs\
│   ├── AGENTS.md            # detailed responsibilities & flows
│   └── CONTEXT.md           # THIS FILE — contracts for parallel dev
├── src\
│   ├── orchestrator\
│   │   ├── graph.py         # LangGraph wiring of all 7 nodes  (Owner: Lead)
│   │   └── state.py         # State schema (TypedDict)         (Owner: Lead)
│   ├── common\
│   │   ├── llm.py           # call_llm() — the one LLM interface (Owner: Lead)
│   │   ├── fs.py            # safe file read/write helpers
│   │   └── logging.py       # shared logger
│   ├── agents\
│   │   ├── code_generation\ # Agent 1   (Owner: Dev A)
│   │   ├── code_review\     # Agent 2   (Owner: Dev B)
│   │   ├── refactoring\     # Agent 3   (Owner: Dev C)
│   │   ├── debugging\       # Agent 4   (Owner: Dev D)
│   │   ├── unit_tests\      # Agent 5   (Owner: Dev E)
│   │   ├── documentation\   # Agent 6   (Owner: Dev F)
│   │   └── security\        # Agent 7   (Owner: Dev G)
│   └── templates\           # Jinja2 templates (used by Agent 1)
├── tests\                   # tests for the agents themselves
├── generated_project\       # OUTPUT: the app the agents build
├── requirements.txt
└── README.md
```

**Rule:** each agent lives in its **own folder** and exposes a single `run(state)`
in an `agent.py`. Nobody edits another agent's folder → no merge conflicts.

---

## 3. The State Contract

This is the **most important part of the doc**. It is the shared object passed
between all agents. Define it once in `src/orchestrator/state.py` and never change
a key's meaning without telling the team.

```python
from typing import TypedDict, List, Dict, Literal, Optional

class Finding(TypedDict):
    file: str
    line: int
    severity: Literal["info", "warning", "error", "critical"]
    message: str
    source: str          # "ruff" | "eslint" | "llm" | "semgrep" ...

class TestResults(TypedDict):
    passed: int
    failed: int
    failures: List[str]  # human-readable failure descriptions

class State(TypedDict, total=False):
    # ---- INPUT ----
    design_package: Dict          # requirements, architecture, entities, endpoints
    language: Literal["python", "react"]
    repo_path: str                # where the generated app lives

    # ---- Agent 1: Code Generation (OWNS) ----
    generated_files: List[str]    # paths of files written

    # ---- Agent 2: Code Review (OWNS) ----
    review_findings: List[Finding]

    # ---- Agent 3: Refactoring (OWNS) ----
    refactor_notes: List[str]

    # ---- Agent 4: Debugging (OWNS) ----
    run_logs: str
    run_success: bool
    debug_attempts: int           # for the retry loop limit

    # ---- Agent 5: Unit Test Generator (OWNS) ----
    test_files: List[str]
    test_results: TestResults

    # ---- Agent 6: Documentation (OWNS) ----
    docs: Dict                    # {"readme": str, "openapi": Optional[str]}

    # ---- Agent 7: Security (OWNS) ----
    security_report: Dict         # {"code": [...], "dependencies": [...]}
```

### Ownership table (who writes what)
| State key | Written by | Read by |
|-----------|-----------|---------|
| `design_package`, `language`, `repo_path` | Orchestrator (input) | All |
| `generated_files` | Agent 1 | 2, 3, 5, 6, 7 |
| `review_findings` | Agent 2 | 3 |
| `refactor_notes` | Agent 3 | (report only) |
| `run_logs`, `run_success`, `debug_attempts` | Agent 4 | orchestrator (loop) |
| `test_files`, `test_results` | Agent 5 | 4 (loop back on fail) |
| `docs` | Agent 6 | (report only) |
| `security_report` | Agent 7 | (report only) |

> **Golden rule restated:** you may READ any key; you may only WRITE the keys your
> agent OWNS.

---

## 4. Agent Interface Contract

Every agent folder must contain an `agent.py` with exactly this shape:

```python
# src/agents/<agent_name>/agent.py
from src.orchestrator.state import State

def run(state: State) -> State:
    """
    Reads:  <list the keys you read>
    Writes: <list the keys you own>
    """
    # 1. read inputs from state
    # 2. do the work (call tools + call_llm)
    # 3. write results into state
    return state
```

That's the only thing the orchestrator needs. As long as your `run(state)` matches
this, the Lead can wire it into the graph even before it's fully implemented (start
with a stub that returns state unchanged).

---

## 5. The One LLM Interface (build this first)

Everyone calls the LLM through **one** function so we can swap Claude ↔ GPT ↔ Ollama
in one place. Owner: Lead. Build on **day 1** — every agent depends on it.

```python
# src/common/llm.py
import os

PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # "anthropic" | "openai" | "ollama"

def call_llm(prompt: str, system: str = "") -> str:
    """Single entry point for all LLM calls. Returns raw text."""
    if PROVIDER == "ollama":
        ...   # local, free
    elif PROVIDER == "anthropic":
        ...   # Claude
    elif PROVIDER == "openai":
        ...   # GPT
    raise ValueError(f"Unknown provider: {PROVIDER}")
```

**Contract:** `call_llm(prompt, system) -> str`. Agents never import `anthropic`,
`openai`, or `ollama` directly — always go through `call_llm`.

---

## 6. Tool Wrappers (so tools are easy to swap/mock)

Wrap each external tool in a small helper that returns **structured Python data**,
not raw text. This lets developers mock tools while building. Suggested wrappers:

| Wrapper | Tool | Returns |
|---------|------|---------|
| `run_ruff(path)` | Ruff | `List[Finding]` |
| `run_eslint(path)` | ESLint | `List[Finding]` |
| `format_python(path)` | Black | None (formats in place) |
| `format_js(path)` | Prettier | None |
| `run_command(cmd)` | subprocess | `(stdout, stderr, exit_code)` |
| `run_pytest(path)` | pytest | `TestResults` |
| `run_jest(path)` | Jest | `TestResults` |
| `run_semgrep(path)` | Semgrep | `List[Finding]` |
| `run_pip_audit(path)` | pip-audit | `List[dict]` |
| `run_npm_audit(path)` | npm audit | `List[dict]` |
| `render_template(name, vars)` | Jinja2 | `str` |
| `commit_files(repo, files, msg)` | GitPython | None |

Most tools are invoked via `run_command` under the hood (they have `--json` /
`--format=json` output that's easy to parse). Put these in
`src/common/tools/` so all agents share them.

---

## 7. Orchestration (LangGraph) — Owner: Lead

```python
# src/orchestrator/graph.py (skeleton)
from langgraph.graph import StateGraph, END
from src.orchestrator.state import State
from src.agents.code_generation.agent import run as code_gen
from src.agents.code_review.agent   import run as code_review
from src.agents.refactoring.agent   import run as refactor
from src.agents.debugging.agent     import run as debug
from src.agents.unit_tests.agent    import run as unit_tests
from src.agents.documentation.agent import run as docs
from src.agents.security.agent      import run as security

MAX_DEBUG_ATTEMPTS = 3

def route_after_tests(state: State) -> str:
    if state["test_results"]["failed"] > 0 and state.get("debug_attempts", 0) < MAX_DEBUG_ATTEMPTS:
        return "debug"          # loop back
    return "docs"

g = StateGraph(State)
g.add_node("code_gen", code_gen)
g.add_node("code_review", code_review)
g.add_node("refactor", refactor)
g.add_node("debug", debug)
g.add_node("unit_tests", unit_tests)
g.add_node("docs", docs)
g.add_node("security", security)

g.set_entry_point("code_gen")
g.add_edge("code_gen", "code_review")
g.add_edge("code_review", "refactor")
g.add_edge("refactor", "debug")
g.add_edge("debug", "unit_tests")
g.add_conditional_edges("unit_tests", route_after_tests, {"debug": "debug", "docs": "docs"})
g.add_edge("docs", "security")
g.add_edge("security", END)

app = g.compile()
```

The retry loop (Testing → Debugging) is the one conditional edge. Everything else
is linear for the POC.

---

## 8. How to Develop in Parallel (the workflow)

1. **Lead builds the foundation first (Sprint 0):**
   `state.py`, `llm.py`, tool wrapper stubs, `graph.py` with all 7 nodes as
   **stubs** (`def run(state): return state`).
2. **Each dev takes one agent folder** (see ownership in §2) and implements
   `run(state)` against the locked State Contract.
3. **Devs test in isolation** using a mock state:
   ```python
   mock = {"language": "python", "repo_path": "generated_project",
           "generated_files": ["main.py"], "design_package": {...}}
   result = run(mock)
   assert "review_findings" in result   # for Agent 2
   ```
4. **Merge:** because each agent is its own folder + honors the contract, merges
   are conflict-free. Replace stubs one by one.
5. **Integration:** Lead runs the full graph end-to-end once ≥2 agents are real.

---

## 9. Setup — Getting Started

**Python deps** (`requirements.txt`):
```
langgraph
gitpython
jinja2
ruff
black
pytest
pip-audit
semgrep
# LLM (pick your provider client)
anthropic      # or openai / ollama
```

**Node deps** (only for React targets, inside `generated_project` or a tools dir):
```
eslint
prettier
jest
# npm audit is built into npm
```

**Environment variables:**
```
LLM_PROVIDER=ollama            # or anthropic / openai
ANTHROPIC_API_KEY=...          # if using Claude
OPENAI_API_KEY=...             # if using GPT
```

**First commands:**
```bash
python -m venv .venv
.venv\Scripts\activate         # Windows PowerShell
pip install -r requirements.txt
```

---

## 10. Definition of Done (per agent, for the POC)

An agent is "done" for the POC when:
- [ ] `run(state)` matches the interface contract.
- [ ] It reads only the keys it needs and writes only the keys it owns.
- [ ] Its tool wrappers return structured data (not raw text).
- [ ] It runs standalone against a mock state without errors.
- [ ] It has one happy-path test in `tests/`.

---

## Quick Reference — Ownership Assignment

| Agent | Folder | Suggested Owner | Depends on (upstream) |
|-------|--------|-----------------|-----------------------|
| Foundation (state, llm, graph) | `orchestrator/`, `common/` | **Lead** | — |
| 1. Code Generation | `agents/code_generation/` | Dev A | design_package |
| 2. Code Review | `agents/code_review/` | Dev B | generated_files |
| 3. Refactoring | `agents/refactoring/` | Dev C | generated_files, review_findings |
| 4. Debugging | `agents/debugging/` | Dev D | generated_files |
| 5. Unit Test Generator | `agents/unit_tests/` | Dev E | generated_files |
| 6. Documentation | `agents/documentation/` | Dev F | generated_files |
| 7. Security | `agents/security/` | Dev G | generated_files |

> Everyone can start the moment the **Lead ships §5 (llm.py) and §3 (state.py)** —
> everything else can be mocked.
