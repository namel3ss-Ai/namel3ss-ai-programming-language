from fastapi.testclient import TestClient

from namel3ss.server import create_app


def test_ui_manifest_endpoint():
    client = TestClient(create_app())
    src = (
        'page "home" at "/":\n'
        '  state name is ""\n'
        '  heading "Hello"\n'
        '  button "Next":\n'
        '    on click:\n'
        '      do flow "go"\n'
    )
    resp = client.post("/api/ui/manifest", headers={"X-API-Key": "dev-key"}, json={"code": src})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ui_manifest_version"] == "1"
    assert data["pages"][0]["route"] == "/"


def test_ui_flow_execute_endpoint():
    client = TestClient(create_app())
    src = (
'flow "echo":\n'
'  step "emit":\n'
'    kind "tool"\n'
'    tool "echo"\n'
'    message "hi"\n'
    )
    resp = client.post("/api/ui/flow/execute", headers={"X-API-Key": "dev-key"}, json={"source": src, "flow": "echo", "args": {"value": 1}})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
