"""Acceptance tests for the IMP-001 subgraph (Prompt 6).

Drives the compiled graph with a FakeExecutor (scripted gate outcomes) and a stubbed LLM
gateway (canned codegen + repair replies) — no Docker, no real model. The executor is injected
via set_executor; the module-singleton nodes use the gateway singleton, which we monkeypatch.
"""

import json

import pytest

from app.graph.graph import workflow
from app.graph.state import new_state
from app.integrations.executor import FakeExecutor, set_executor
from app.models import WorkItem
from app.services import llm_gateway

LOGIN_ITEM = WorkItem(
    id="WI-001",
    requirement_ids=["REQ-1"],
    endpoints=["POST /login"],
    tables=["users"],
    target_files=["app/api/login.py"],
)
CODEGEN_JSON = json.dumps({"files": [{"path": "app/api/login.py", "content": "# v1\n"}], "notes": ""})
# Repair is shown the files by their real (project-prefixed) paths and echoes them back.
REPAIR_JSON = json.dumps({"files": [{"path": "p1/app/api/login.py", "content": "# v2 fixed\n"}], "notes": "fixed"})


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch):
    # codegen uses complete(); repair uses complete_with_tools() — stub both on the singleton.
    monkeypatch.setattr(llm_gateway.llm_gateway, "complete", lambda *a, **k: CODEGEN_JSON)
    monkeypatch.setattr(llm_gateway.llm_gateway, "complete_with_tools", lambda *a, **k: REPAIR_JSON)
    yield
    set_executor(None)


def _run(executor: FakeExecutor, thread_id: str) -> dict:
    set_executor(executor)
    initial = new_state(run_id="run-1", attempt=7, project_id="p1")
    initial["work_items"] = [LOGIN_ITEM]
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
    workflow.invoke(initial, config)
    return dict(workflow.get_state(config).values)


def test_fail_once_then_pass_repairs_once_and_commits_once() -> None:
    # compile fails first, passes on retry; build/test/lint pass by default.
    executor = FakeExecutor(compile_results=[False, True])
    final = _run(executor, "t-happy")

    assert final["repair_attempt"] == 1                  # exactly one repair
    assert executor.commits == [                          # committed exactly once, on all-pass
        ("p1", "IMP-001 WI-001: p1/app/api/login.py")
    ]
    assert final["workflow_status"] == "code_reviewed"    # plan exhausted -> final review ran
    assert final["attempt"] == 7                          # orchestrator's counter echoed unchanged
    # the repair's proposed content was written back through the executor
    assert executor.files["p1/app/api/login.py"] == "# v2 fixed\n"


def test_always_fails_stops_at_cap_needs_human_review_no_commit() -> None:
    executor = FakeExecutor(default_pass=False)          # every check fails, always
    final = _run(executor, "t-cap")

    assert final["workflow_status"] == "needs_human_review"
    assert final["repair_attempt"] == 3                   # == REPAIR_CAP
    assert executor.commits == []                         # NO commit on the escalation path


def test_bad_codegen_escalates_without_reaching_gate(monkeypatch) -> None:
    # A generation that never yields valid JSON must NOT reach the gate or commit.
    monkeypatch.setattr(llm_gateway.llm_gateway, "complete", lambda *a, **k: "not json at all")
    executor = FakeExecutor()
    final = _run(executor, "t-badcodegen")

    assert final["generated_code"] == []                  # nothing written
    assert final["workflow_status"] == "needs_human_review"
    assert executor.commits == []                          # no commit
    assert executor.commands == []                         # gate never ran a check (no compile call)
