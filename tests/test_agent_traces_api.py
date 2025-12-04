from fastapi.testclient import TestClient

from namel3ss.server import create_app


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
)


def _run_agent_and_get_client() -> TestClient:
    client = TestClient(create_app())
    client.post(
        "/api/run-app",
        json={"source": PROGRAM_TEXT, "app_name": "support_portal"},
        headers={"X-API-Key": "dev-key"},
    )
    return client


def test_agent_traces_endpoint_returns_list():
    client = _run_agent_and_get_client()
    resp = client.get("/api/agent-traces", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    traces = resp.json()
    assert isinstance(traces, list)
    assert len(traces) >= 1
    first = traces[0]
    assert "id" in first
    assert "agent_name" in first


def test_agent_trace_by_id_endpoint_returns_detail():
    client = _run_agent_and_get_client()
    list_resp = client.get("/api/agent-traces", headers={"X-API-Key": "dev-key"})
    trace_id = list_resp.json()[0]["id"]
    detail_resp = client.get(f"/api/agent-trace/{trace_id}", headers={"X-API-Key": "dev-key"})
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["id"] == trace_id
    assert "steps" in body
    if body["steps"]:
        step = body["steps"][0]
        assert "step_name" in step
        assert "kind" in step


def test_agent_trace_by_id_not_found():
    client = _run_agent_and_get_client()
    resp = client.get("/api/agent-trace/does-not-exist", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 404
