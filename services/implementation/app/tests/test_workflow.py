"""End-to-end test of the /implementation/start path with a stubbed LLM,
so it runs without a real ANTHROPIC_API_KEY or network calls.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_gateway import llm_gateway

client = TestClient(app)


def test_start_runs_code_generation(monkeypatch):
    monkeypatch.setattr(
        llm_gateway, "complete", lambda *a, **k: "print('generated')"
    )

    response = client.post(
        "/implementation/start",
        json={"project_id": "p1", "design_package": "A CLI todo app"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "p1"
    assert body["workflow_status"] == "code_generated"
    assert body["generated_code"] == "print('generated')"
