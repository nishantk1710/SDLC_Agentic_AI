# Implementation Service

## Overview

The **Implementation Service** is responsible for transforming the **Design Package** into a complete **Implementation Package**.

It is an independent microservice within the AI SDLC platform and is built using:

* **FastAPI** – REST APIs
* **LangGraph** – Workflow orchestration
* **Python** – Agent implementation
* **LLM (Claude/GPT)** – Code generation and reasoning
* **PostgreSQL** – Metadata & workflow state
* **Shared Workspace** – Artifact storage

The service follows a modular architecture where **FastAPI exposes APIs**, **LangGraph orchestrates the workflow**, and **agents perform individual implementation tasks**.

---

# Tech Stack

| Layer               | Technology   |
| ------------------- | ------------ |
| Language            | Python 3.12+ |
| API Framework       | FastAPI      |
| Agent Orchestration | LangGraph    |
| Validation          | Pydantic     |
| LLM                 | Claude / GPT |
| Database            | PostgreSQL   |
| Version Control     | GitHub       |
| Security Scan       | Semgrep      |
| Code Quality        | SonarQube    |
| Testing             | pytest       |
| Containerization    | Docker       |

---

# Responsibilities

The Implementation Service is responsible for:

* Reading the Design Package
* Generating application source code
* Reviewing generated code
* Refactoring code
* Debugging implementation issues
* Generating unit tests
* Generating documentation
* Running security analysis
* Producing the final Implementation Package

---

# High-Level Workflow

```text
Design Package
      │
      ▼
Code Generation Agent
      │
      ▼
Code Review Agent
      │
      ▼
Refactoring Agent
      │
      ▼
Debugging Agent
      │
      ▼
Unit Test Generator
      │
      ▼
Documentation Agent
      │
      ▼
Security Agent
      │
      ▼
Implementation Package
```

LangGraph orchestrates the above workflow.

---

# Folder Structure

```text
implementation-service/

app/

├── main.py

├── api/
│   ├── routes.py
│   ├── request_models.py
│   └── response_models.py

├── graph/
│   ├── graph.py
│   ├── state.py
│   ├── nodes.py
│   └── router.py

├── agents/
│   ├── base.py
│   ├── code_generator.py
│   ├── code_review.py
│   ├── refactoring.py
│   ├── debugging.py
│   ├── unit_test.py
│   ├── documentation.py
│   └── security.py

├── services/
│   ├── llm_gateway.py
│   ├── artifact_service.py
│   ├── workspace_service.py
│   ├── parser.py
│   └── retriever.py

├── integrations/
│   ├── github.py
│   ├── figma.py
│   ├── semgrep.py
│   ├── sonarqube.py
│   ├── pytest_runner.py
│   └── docker.py

├── prompts/

├── templates/

├── workspace/

├── models/

├── config/

├── utils/

└── tests/
```

---

# Architecture

## FastAPI

Responsible for:

* Exposing REST APIs
* Request validation
* Authentication (future)
* Calling LangGraph
* Returning responses

FastAPI **does not contain agent logic**.

---

## LangGraph

LangGraph is the workflow engine of the service.

Responsibilities:

* Execute agents in sequence
* Maintain workflow state
* Route based on decisions
* Retry failed steps
* Return final execution result

LangGraph **does not generate code**.

---

## Agents

Agents perform the actual work.

Current agents:

* Code Generation Agent
* Code Review Agent
* Refactoring Agent
* Debugging Agent
* Unit Test Generator Agent
* Documentation Agent
* Security Agent

Each agent follows a common interface:

```python
execute(state) -> state
```

Each agent receives the current workflow state, performs its task, updates the state, and returns it.

---

# Shared Workflow State

The LangGraph state contains metadata and artifact locations.

Typical fields include:

* Project ID
* Design Package
* Generated Code
* Review Report
* Refactored Code
* Unit Tests
* Documentation
* Security Report
* Workflow Status

Agents should update only the fields they own.

---

# Services

## llm_gateway

Centralized LLM communication.

Responsibilities:

* Prompt execution
* Retry handling
* Token management
* Provider abstraction
* Logging

No agent should call the LLM directly.

---

## artifact_service

Responsible for:

* Reading Design Package
* Saving generated artifacts
* Packaging outputs
* Loading previous artifacts

---

## workspace_service

Responsible for:

* Project workspace creation
* Temporary file management
* Cleanup
* Archive generation

---

## parser

Parses existing source code for analysis.

---

## retriever

Provides retrieval-augmented context for the LLM.

---

# Integrations

The `integrations` module wraps all external systems.

Examples:

* GitHub
* Figma
* Semgrep
* SonarQube
* pytest
* Docker

Business logic should never directly invoke external tools.

---

# Prompts

Contains version-controlled prompts for every LLM-powered agent.

Example:

* code_generation.md
* code_review.md
* debugging.md
* documentation.md
* security.md

---

# Templates

Contains starter templates for supported technology stacks.

Examples:

* React
* FastAPI
* Spring Boot
* Node.js

---

# Workspace

Stores temporary project artifacts during execution.

Example:

```text
workspace/

project-001/

design_package/

generated_code/

unit_tests/

reports/
```

---

# API Endpoints

Example endpoints:

```
POST /implementation/start

GET /implementation/status/{projectId}

GET /implementation/result/{projectId}

POST /implementation/retry
```

---

# Development Guidelines

* Keep each agent focused on a single responsibility.
* Do not embed workflow logic inside agents.
* Do not call the LLM directly from agents; use `llm_gateway`.
* Keep business logic separate from API routes.
* Keep external tool interactions inside `integrations`.
* Store generated artifacts in the workspace.
* Update only the relevant fields in the shared LangGraph state.
* Write unit tests for every new module.

---

# Execution Flow

```text
Client Request
      │
      ▼
FastAPI API
      │
      ▼
LangGraph Workflow
      │
      ▼
Agents
      │
      ▼
Workspace & External Integrations
      │
      ▼
Implementation Package
      │
      ▼
Response
```

---

# Future Enhancements

* Human-in-the-Loop approvals
* Multi-LLM support
* Distributed execution
* Agent memory
* Parallel agent execution
* Plugin-based agent architecture
* CI/CD integration
* Incremental code generation

---

# Coding Standards

* Follow PEP 8.
* Use type hints.
* Prefer dependency injection where appropriate.
* Keep functions small and focused.
* Add meaningful logging.
* Write tests for all new features.
* Keep modules loosely coupled and reusable.
