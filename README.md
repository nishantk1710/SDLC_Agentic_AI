# SDLC_Agentic_AI

AI-powered SDLC lifecycle automation using autonomous agents to streamline
planning, development, testing, code review, documentation, deployment, and
project workflows.

## What this is

Four SDLC phases, each owned by one team and implemented as an independent
microservice. A LangGraph **orchestrator** routes work phase-to-phase, runs
human approval gates, and handles the retry loop. Teams integrate through
versioned **contracts** — the handoff schemas are the product.

```
Requirements ──▶ Design ──▶ Implementation ──▶ Testing
 (Team 1)       (Team 2)      (Team 3)          (Team 4)
```

## Repository layout

```
SDLC_Agentic_AI/
├─ apps/
│  ├─ api-gateway/               FastAPI gateway — auth, projects, jobs, status
│  └─ web/                       React + TS shell (one module per phase)
│     └─ src/modules/
│        ├─ requirements/
│        ├─ design/
│        ├─ implementation/
│        └─ testing/
│
├─ orchestrator/                 LangGraph pipeline — routes phases, retry loop, gates
│  ├─ graph/                     StateGraph: nodes = phases, edges = handoffs
│  ├─ gates/                     human-in-the-loop approval gates
│  └─ loops/                     FAIL → Implementation retry counter, ERROR → human
│
├─ services/                     the four phase microservices (one per team)
│  ├─ requirements/              Team 1 — RGA (docs → SRS + RTM)
│  ├─ design/                    Team 2 — SRS → 18-artifact design pack
│  ├─ implementation/            Team 3 — design pack → working code
│  └─ testing/                   Team 4 — code → PASS / FAIL / ERROR verdict
│
├─ contracts/                    handoff schemas — the product; all teams review
│  ├─ shared/                    AgentResponse envelope, run metadata, ID rules
│  ├─ requirements-to-design/
│  ├─ design-to-implementation/  ← Implementation INPUT (27 inputs, 20 mandatory)
│  └─ implementation-to-testing/ ← Implementation OUTPUT (A1–A7 + tech-stack.json)
│
├─ packages/                     shared libs across services
│  ├─ schemas/                   generated TS/Pydantic types from contracts
│  ├─ config/
│  └─ logging/
│
├─ infra/
│  ├─ db/                        pgvector init scripts
│  ├─ migrations/                Alembic migrations
│  └─ ci/                        shared CI configs
│
├─ docs/                         architecture, ADRs, runbooks
├─ .github/workflows/            GitHub Actions
├─ docker-compose.yml            PostgreSQL + pgvector + Redis for local dev
├─ .env.example
├─ CODEOWNERS                    one team per service folder; contracts = all teams
├─ CONTRIBUTING.md               branching model + PR rules
└─ README.md
```

## Team ownership

| Folder                     | Team   | Responsibility                          |
| -------------------------- | ------ | --------------------------------------- |
| `services/requirements/`   | Team 1 | Docs → SRS + RTM                        |
| `services/design/`         | Team 2 | SRS → 18-artifact design pack           |
| `services/implementation/` | Team 3 | Design pack → working code              |
| `services/testing/`        | Team 4 | Code → PASS / FAIL / ERROR verdict      |
| `contracts/`               | All    | Handoff schemas — changes reviewed by everyone |

## Getting started

```bash
git clone https://github.com/nishantk1710/SDLC_Agentic_AI.git
cd SDLC_Agentic_AI
cp .env.example .env
docker compose up -d          # PostgreSQL + pgvector + Redis
```

Then work inside your team's folder. Read [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the branching model and PR rules before opening a pull request.

> **Status:** scaffolding only. Every folder currently holds a placeholder
> `README.md` describing its purpose — no application code yet.
