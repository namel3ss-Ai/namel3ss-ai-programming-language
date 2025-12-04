from fastapi.testclient import TestClient

from namel3ss.server import create_app


def _client():
    return TestClient(create_app())


def test_plugins_endpoint_returns_list():
    client = _client()
    resp = client.get("/api/plugins", headers={"X-API-Key": "viewer-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert "plugins" in body
    assert isinstance(body["plugins"], list)


def test_plugins_items_have_required_fields_when_present():
    client = _client()
    resp = client.get("/api/plugins", headers={"X-API-Key": "viewer-key"})
    assert resp.status_code == 200
    plugins = resp.json().get("plugins", [])
    if plugins:
        plugin = plugins[0]
        assert "id" in plugin
        assert "name" in plugin
        assert "version" in plugin

