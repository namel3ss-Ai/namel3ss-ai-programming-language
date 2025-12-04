from fastapi.testclient import TestClient

from namel3ss.server import create_app


PROGRAM_TEXT = (
    'flow "pipeline":\n'
    '  step "call":\n'
    '    kind "ai"\n'
    '    target "summarise_message"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
)


def _run_flow_and_get_client() -> TestClient:
    client = TestClient(create_app())
    client.post(
        "/api/run-flow",
        json={"source": PROGRAM_TEXT, "flow": "pipeline"},
        headers={"X-API-Key": "dev-key"},
    )
    return client


def test_traces_endpoint_returns_list():
    client = _run_flow_and_get_client()
    resp = client.get("/api/traces", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    traces = resp.json()
    assert isinstance(traces, list)
    assert len(traces) >= 1
    first = traces[0]
    assert "id" in first
    assert "started_at" in first


def test_trace_by_id_endpoint_returns_full_trace():
    client = _run_flow_and_get_client()
    list_resp = client.get("/api/traces", headers={"X-API-Key": "dev-key"})
    trace_id = list_resp.json()[0]["id"]
    detail_resp = client.get(f"/api/trace/{trace_id}", headers={"X-API-Key": "dev-key"})
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["id"] == trace_id
    assert "trace" in body


def test_trace_by_id_not_found():
    client = _run_flow_and_get_client()
    resp = client.get("/api/trace/does-not-exist", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 404
