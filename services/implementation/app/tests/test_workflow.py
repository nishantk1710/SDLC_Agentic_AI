"""Smoke test of the /implementation/start route + compiled graph.

With no work item in the state, the Code Generation agent is a clean no-op (the graph loop that
sets current_work_item per item is built in a later prompt). Real code generation is covered by
test_code_generator.py. This test just proves the route + graph run and return cleanly, with no
LLM or sandbox needed.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_start_route_runs_cleanly() -> None:
    response = client.post(
        "/implementation/start",
        json={"project_id": "p1", "design_package": {"SKILL.md": "conventions"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "p1"
    assert body["run_id"]                       # a run id was assigned
    assert body["generated_code"] == []         # no work items -> nothing generated
    assert body["workflow_status"] == "completed"   # empty plan -> select exhausts immediately
