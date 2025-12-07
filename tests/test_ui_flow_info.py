from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.server import create_app


def _client(tmp_path: Path) -> TestClient:
    import os

    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        return TestClient(create_app())
    finally:
        os.chdir(prev)


def test_ui_flow_info(tmp_path: Path):
    (tmp_path / "flows").mkdir()
    (tmp_path / "flows" / "demo.ai").write_text('flow "demo":\n  step "s":\n    log info "ok"\n', encoding="utf-8")
    client = _client(tmp_path)
    resp = client.get("/api/ui/flow/info", params={"name": "demo"}, headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "demo"
    assert "args" in data


def test_ui_flow_info_not_found(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.get("/api/ui/flow/info", params={"name": "missing"}, headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 404
