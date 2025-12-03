from fastapi.testclient import TestClient

from namel3ss.server import create_app


def test_optimizer_requires_auth_and_role(tmp_path, monkeypatch):
    monkeypatch.setenv("N3_OPTIMIZER_DB", str(tmp_path / "opt.db"))
    monkeypatch.setenv("N3_OPTIMIZER_OVERLAYS", str(tmp_path / "overlays.json"))
    client = TestClient(create_app())
    resp = client.get("/api/optimizer/suggestions")
    assert resp.status_code == 401
    resp = client.get("/api/optimizer/suggestions", headers={"X-API-Key": "viewer-key"})
    assert resp.status_code == 403
    resp = client.get("/api/optimizer/suggestions", headers={"X-API-Key": "dev-key"})
    assert resp.status_code == 200


def test_plugins_and_triggers_enforce_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("N3_OPTIMIZER_DB", str(tmp_path / "opt.db"))
    monkeypatch.setenv("N3_OPTIMIZER_OVERLAYS", str(tmp_path / "overlays.json"))
    client = TestClient(create_app())
    resp = client.get("/api/plugins")
    assert resp.status_code == 401
    resp = client.get("/api/flows/triggers")
    assert resp.status_code == 401
    resp = client.get("/api/plugins", headers={"X-API-Key": "viewer-key"})
    assert resp.status_code == 200
    resp = client.get("/api/flows/triggers", headers={"X-API-Key": "viewer-key"})
    assert resp.status_code == 200
