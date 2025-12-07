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


def test_ui_flow_execute_success(tmp_path: Path):
    (tmp_path / "flows").mkdir()
    (tmp_path / "flows" / "hello.ai").write_text(
        'flow "hello":\n  step "s":\n    log info "hi"\n', encoding="utf-8"
    )
    client = _client(tmp_path)
    resp = client.post(
        "/api/ui/flow/execute",
        headers={"X-API-Key": "dev-key"},
        json={"flow": "hello", "args": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_ui_flow_execute_unknown(tmp_path: Path):
    client = _client(tmp_path)
    resp = client.post(
        "/api/ui/flow/execute",
        headers={"X-API-Key": "dev-key"},
        json={"flow": "missing", "args": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
