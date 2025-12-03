import json

from fastapi.testclient import TestClient

from namel3ss.server import create_app


def test_server_diagnostics_strict_and_json():
    client = TestClient(create_app())
    code = 'page "home":\n  title "Home"\n'
    resp = client.post(
        "/api/diagnostics",
        params={"strict": "true", "format": "json"},
        headers={"X-API-Key": "dev-key"},
        json={"code": code},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data and "diagnostics" in data
    assert data["summary"]["strict"] is True
    assert data["summary"]["warning_count"] >= 1
    assert any(d["code"].startswith("N3-") for d in data["diagnostics"])


def test_server_diagnostics_text_format():
    client = TestClient(create_app())
    code = 'flow "pipeline":\n'
    resp = client.post(
        "/api/diagnostics",
        params={"format": "text"},
        headers={"X-API-Key": "dev-key"},
        json={"code": code},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "[N3-" in data["text"]
