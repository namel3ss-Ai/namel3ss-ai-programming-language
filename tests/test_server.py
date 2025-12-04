import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.server import create_app


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    '  memory "short_term"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
)


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse_endpoint_returns_ast():
    client = TestClient(create_app())
    response = client.post("/api/parse", json={"source": PROGRAM_TEXT})
    assert response.status_code == 200
    assert "ast" in response.json()


def test_run_app_endpoint_returns_execution():
    client = TestClient(create_app())
    response = client.post(
        "/api/run-app",
        json={"source": PROGRAM_TEXT, "app_name": "support_portal"},
        headers={"X-API-Key": "dev-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["app"]["status"] == "ok"
    assert body["result"]["entry_page"]["status"] == "ok"
    trace = body["trace"]
    assert trace
    assert trace["pages"][0]["agents"]


def test_last_trace_endpoint_after_run():
    client = TestClient(create_app())
    client.post(
        "/api/run-app",
        json={"source": PROGRAM_TEXT, "app_name": "support_portal"},
        headers={"X-API-Key": "dev-key"},
    )
    trace_response = client.get("/api/last-trace", headers={"X-API-Key": "dev-key"})
    assert trace_response.status_code == 200
    assert trace_response.json()["trace"]["app_name"] == "support_portal"
    assert trace_response.json()["trace"]["pages"][0]["agents"]


def test_run_flow_endpoint():
    flow_program = (
        'flow "pipeline":\n'
        '  step "call":\n'
        '    kind "ai"\n'
        '    target "summarise_message"\n'
        'model "default":\n'
        '  provider "openai:gpt-4.1-mini"\n'
        'ai "summarise_message":\n'
        '  model "default"\n'
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/run-flow",
        json={"source": flow_program, "flow": "pipeline"},
        headers={"X-API-Key": "dev-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["flow_name"] == "pipeline"
    assert body["result"]["steps"][0]["success"] is True


def test_pages_endpoint_lists_pages():
    code = (
        'page "home":\n'
        '  title "Home"\n'
        '  route "/"\n'
        'page "about":\n'
        '  title "About"\n'
        '  route "/about"\n'
    )
    client = TestClient(create_app())
    response = client.post("/api/pages", json={"code": code}, headers={"X-API-Key": "viewer-key"})
    assert response.status_code == 200
    names = [p["name"] for p in response.json()["pages"]]
    assert "home" in names and "about" in names


def test_page_ui_endpoint_returns_sections():
    code = (
        'page "home":\n'
        '  title "Home"\n'
        '  route "/"\n'
        '  section "hero":\n'
        '    component "text":\n'
        '      value "Welcome"\n'
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/page-ui", json={"code": code, "page": "home"}, headers={"X-API-Key": "viewer-key"}
    )
    assert response.status_code == 200
    ui = response.json()["ui"]
    assert ui["sections"]


def test_meta_endpoint_returns_info():
    client = TestClient(create_app())
    response = client.get("/api/meta", headers={"X-API-Key": "dev-key"})
    assert response.status_code == 200
    body = response.json()
    assert "ai" in body and "plugins" in body


def test_metrics_and_studio_endpoints():
    client = TestClient(create_app())
    metrics_resp = client.get("/api/metrics", headers={"X-API-Key": "dev-key"})
    assert metrics_resp.status_code == 200
    studio_resp = client.get("/api/studio-summary", headers={"X-API-Key": "viewer-key"})
    assert studio_resp.status_code == 200
    assert "summary" in studio_resp.json()


def test_diagnostics_and_bundle_endpoints():
    code = (
        'page "home":\n'
        '  title "Home"\n'
        '  route "/"\n'
        'flow "pipeline":\n'
        '  step "call":\n'
        '    kind "ai"\n'
        '    target "summarise_message"\n'
        'model "default":\n'
        '  provider "openai:gpt-4.1-mini"\n'
        'ai "summarise_message":\n'
        '  model "default"\n'
    )
    tmp = Path(tempfile.mkdtemp())
    program_file = tmp / "program.ai"
    program_file.write_text(code, encoding="utf-8")
    client = TestClient(create_app())
    diag_resp = client.post(
        "/api/diagnostics", json={"paths": [str(program_file)]}, headers={"X-API-Key": "dev-key"}
    )
    assert diag_resp.status_code == 200
    assert "diagnostics" in diag_resp.json()
    bundle_resp = client.post(
        "/api/bundle", json={"code": code, "target": "server"}, headers={"X-API-Key": "dev-key"}
    )
    assert bundle_resp.status_code == 200
    assert bundle_resp.json()["bundle"]["type"] == "server"
