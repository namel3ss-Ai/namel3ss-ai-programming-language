from fastapi.testclient import TestClient

from namel3ss.server import create_app


def test_example_source_success():
    client = TestClient(create_app())
    resp = client.get("/api/example-source", params={"name": "hello_world"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "hello_world"
    assert "examples/hello_world/hello_world.ai" in data["path"]
    assert data["source"]


def test_example_source_missing():
    client = TestClient(create_app())
    resp = client.get("/api/example-source", params={"name": "does_not_exist"})
    assert resp.status_code == 404
    assert "does_not_exist" in resp.json().get("detail", "")
