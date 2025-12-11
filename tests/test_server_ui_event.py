from fastapi.testclient import TestClient

from namel3ss.server import create_app


PROGRAM = (
    'flow is "pipeline":\n'
    '  step is "call":\n'
    '    kind is "ai"\n'
    '    target is "summarise_message"\n'
    'page is "home" at "/":\n'
    '  title "Home"\n'
    '  section "hero":\n'
    '    component "form":\n'
    '      value "name!"\n'
    '      target is "pipeline"\n'
    'model is "default":\n'
    '  provider is "openai_default"\n'
    'ai is "summarise_message":\n'
    '  model is "default"\n'
)


def test_ui_event_endpoint_handles_submit():
    client = TestClient(create_app())
    ui = client.post("/api/page-ui", json={"code": PROGRAM, "page": "home"}, headers={"X-API-Key": "viewer-key"})
    assert ui.status_code == 200
    components = ui.json().get("components", [])
    assert components
    comp_id = components[0]["id"]
    resp = client.post(
        "/api/ui/event",
        json={
            "code": PROGRAM,
            "page": "home",
            "component_id": comp_id,
            "event": "submit",
            "payload": {"name": "Ada"},
        },
        headers={"X-API-Key": "viewer-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["success"] is True
