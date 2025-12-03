from fastapi.testclient import TestClient

from namel3ss.server import create_app


def test_requires_api_key_for_run_app():
    client = TestClient(create_app())
    response = client.post("/api/run-app", json={"source": "", "app_name": "x"})
    assert response.status_code == 401


def test_forbidden_for_flow_as_viewer():
    client = TestClient(create_app())
    response = client.post(
        "/api/run-flow",
        json={"source": "", "flow": "x"},
        headers={"X-API-Key": "viewer-key"},
    )
    assert response.status_code == 403


def test_meta_requires_developer():
    client = TestClient(create_app())
    response = client.get("/api/meta", headers={"X-API-Key": "viewer-key"})
    assert response.status_code == 403
    response2 = client.get("/api/meta", headers={"X-API-Key": "dev-key"})
    assert response2.status_code == 200
