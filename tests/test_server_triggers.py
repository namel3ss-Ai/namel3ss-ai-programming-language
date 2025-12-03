from fastapi.testclient import TestClient

from namel3ss.server import create_app


def test_http_trigger_endpoint_enqueues_job():
    client = TestClient(create_app())
    # register a trigger
    client.post(
        "/api/flows/triggers",
        json={"id": "t-http", "kind": "http", "flow_name": "flow_x", "config": {}, "enabled": True},
        headers={"X-API-Key": "dev-key"},
    )
    response = client.post(
        "/api/flows/trigger/t-http",
        json={"payload": {"foo": "bar"}},
        headers={"X-API-Key": "dev-key"},
    )
    assert response.status_code == 200
    assert response.json()["job_id"] is not None
