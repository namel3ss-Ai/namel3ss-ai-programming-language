import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from namel3ss.server import create_app
from namel3ss.studio.daemon import StudioDaemon
import namel3ss.runtime.context as runtime_context
import namel3ss.memory.inspection as mem_inspection


PROGRAM_TEXT = (
    'app is "support_portal":\n'
    '  entry_page is "home"\n'
    'page is "home" at "/":\n'
    '  title "Home"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    '  memory "short_term"\n'
    'model is "default":\n'
    '  provider is "openai_default"\n'
    'ai is "summarise_message":\n'
    '  model is "default"\n'
    'agent is "helper":\n'
    '  goal "Assist"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
)


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_studio_status_endpoint_valid_program(tmp_path: Path):
    (tmp_path / "app.ai").write_text(PROGRAM_TEXT, encoding="utf-8")
    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/studio/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_root"] == str(tmp_path.resolve())
    assert payload["ai_files"] == 1
    assert payload["ir_status"] == "valid"
    assert payload["studio_static_available"] is not None


def test_studio_status_endpoint_handles_ir_errors(tmp_path: Path):
    (tmp_path / "app.ai").write_text("this is not valid ai syntax", encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=False)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))
    response = client.get("/api/studio/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ir_status"] == "error"
    assert payload.get("ir_error")


def test_studio_logs_stream(tmp_path: Path):
    daemon = StudioDaemon(tmp_path)
    daemon.logs.append("daemon_started", level="info")
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))
    with client.stream("GET", "/api/studio/logs/stream?once=1") as resp:
        assert resp.status_code == 200
        first = next(resp.iter_text())
        assert "daemon_started" in first


def test_studio_canvas_manifest(tmp_path: Path):
    program_text = (
        'app is "support":\n'
        '  entry_page is "home"\n'
        'page is "home" at "/":\n'
        '  title "Home"\n'
        '  ai_call "summarise"\n'
        'flow is "pipeline":\n'
        '  step is "call":\n'
        '    kind is "ai"\n'
        '    target "summarise"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "summarise":\n'
        '  model is "default"\n'
    )
    (tmp_path / "app.ai").write_text(program_text, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=True)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))
    resp = client.get("/api/studio/canvas")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["nodes"]
    assert any(n["kind"] == "app" for n in payload["nodes"])
    assert any(e["kind"].endswith("ai") or e["kind"] == "ai_step" for e in payload["edges"])


def test_inspector_page_and_flow(tmp_path: Path):
    program_text = (
        'app is "support":\n'
        '  entry_page is "home"\n'
        'page is "home" at "/":\n'
        '  title "Home"\n'
        '  ai_call "summarise"\n'
        'flow is "pipeline":\n'
        '  step is "call":\n'
        '    kind is "ai"\n'
        '    target "summarise"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "summarise":\n'
        '  model is "default"\n'
    )
    (tmp_path / "app.ai").write_text(program_text, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=True)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))

    page_resp = client.get("/api/studio/inspect", params={"kind": "page", "name": "home"})
    assert page_resp.status_code == 200
    page_data = page_resp.json()
    assert page_data["kind"] == "page"
    assert page_data["route"] == "/"
    flow_resp = client.get("/api/studio/inspect", params={"kind": "flow", "name": "pipeline"})
    assert flow_resp.status_code == 200
    flow_data = flow_resp.json()
    assert flow_data["steps"] == 1
    assert flow_data["ai_calls"] == ["summarise"]

    missing_resp = client.get("/api/studio/inspect", params={"kind": "page", "name": "missing"})
    assert missing_resp.status_code == 404


def test_studio_flows_and_run_flow(tmp_path: Path):
    program_text = (
        'flow is "pipeline":\n'
        '  step is "call":\n'
        '    kind is "ai"\n'
        '    target "summarise_message"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "summarise_message":\n'
        '  model is "default"\n'
    )
    (tmp_path / "app.ai").write_text(program_text, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=True)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))

    list_resp = client.get("/api/studio/flows")
    assert list_resp.status_code == 200
    flows = list_resp.json().get("flows") or []
    assert any(f["name"] == "pipeline" for f in flows)

    run_resp = client.post("/api/studio/run-flow", json={"flow": "pipeline"})
    assert run_resp.status_code == 200
    run_payload = run_resp.json()
    assert run_payload["flow"] == "pipeline"
    assert isinstance(run_payload.get("steps"), list)
    assert run_payload.get("errors") is not None

    missing_resp = client.post("/api/studio/run-flow", json={"flow": "missing"})
    assert missing_resp.status_code == 404


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
        'flow is "pipeline":\n'
        '  step is "call":\n'
        '    kind is "ai"\n'
        '    target "summarise_message"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "summarise_message":\n'
        '  model is "default"\n'
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


def test_memory_plan_sessions_and_state(tmp_path: Path):
    program_text = (
        'ai is "with_memory":\n'
        '  model is "default"\n'
        '  memory "short_term"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'memory "short_term":\n'
        '  type "conversation"\n'
    )
    (tmp_path / "app.ai").write_text(program_text, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=True)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))

    ais_resp = client.get("/api/memory/ais", headers={"X-API-Key": "viewer-key"})
    assert ais_resp.status_code == 200
    ais = ais_resp.json().get("ais") or []
    assert any(entry["id"] == "with_memory" for entry in ais)

    plan_resp = client.get("/api/memory/ai/with_memory/plan", headers={"X-API-Key": "viewer-key"})
    assert plan_resp.status_code == 200
    plan = plan_resp.json()
    assert plan["ai"] == "with_memory"
    assert plan["has_memory"] is True

    sessions_resp = client.get("/api/memory/ai/with_memory/sessions", headers={"X-API-Key": "viewer-key"})
    assert sessions_resp.status_code == 200
    sessions_payload = sessions_resp.json()
    assert "sessions" in sessions_payload

    state_resp = client.get("/api/memory/ai/with_memory/state", params={"session_id": "test-session"}, headers={"X-API-Key": "viewer-key"})
    assert state_resp.status_code == 200
    state = state_resp.json()
    assert state["ai"] == "with_memory"
    assert state.get("kinds") is not None


def test_ask_studio_endpoint(monkeypatch):
    def fake_call(question, status=None, entity=None, logs=None, flow_run=None, memory=None, memory_state=None, model=None, router=None, mode="explain"):
        return {"answer": "Stubbed answer", "suggested_snippets": [{"title": "t", "dsl": "flow is \"x\""}]}

    monkeypatch.setattr("namel3ss.server.ask_studio", fake_call)
    client = TestClient(create_app())
    resp = client.post("/api/studio/ask", json={"question": "Why?", "context": {"kind": "flow", "name": "checkout"}})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["answer"] == "Stubbed answer"


def test_ask_studio_generation_mode(monkeypatch):
    def fake_call(question, status=None, entity=None, logs=None, flow_run=None, memory=None, memory_state=None, model=None, router=None, mode="explain"):
        assert mode == "generate_flow"
        return {
          "answer": "Here is a flow.\n```flow is \"checkout\":\n  step is \"one\":\n    kind is \"ai\"\n    target \"do\"\n```",
            "suggested_snippets": [
                {"title": "flow", "dsl": "flow is \"checkout\":\n  step is \"one\":\n    kind is \"ai\"\n    target \"do\"", "kind": "flow"}
            ],
            "mode": mode,
        }

    monkeypatch.setattr("namel3ss.server.ask_studio", fake_call)
    client = TestClient(create_app())
    resp = client.post("/api/studio/ask", json={"question": "build a flow", "mode": "generate_flow"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("mode") == "generate_flow"
    snippets = payload.get("suggested_snippets") or []
    assert snippets and snippets[0]["kind"] == "flow"


def test_studio_warnings_endpoint(tmp_path: Path):
    program_text = (
        'tool is "charge":\n'
        '  kind is "http"\n'
        '  method is "POST"\n'
        '  url is "https://api.example.com/pay"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "dummy":\n'
        '  model is "default"\n'
        'flow is "checkout":\n'
        '  step is "pay":\n'
        '    kind is "ai"\n'
        '    target "dummy"\n'
    )
    (tmp_path / "app.ai").write_text(program_text, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=True)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))
    resp = client.get("/api/studio/warnings")
    assert resp.status_code == 200
    warnings = resp.json().get("warnings") or []
    assert warnings
    codes = {w["code"] for w in warnings}
    assert "N3-BP-1001" in codes  # flow without error handling
    assert "N3-BP-2001" in codes  # tool no auth


def test_ai_call_visualizer_endpoint(monkeypatch, tmp_path: Path):
    program_text = (
        'app is "support":\n'
        '  entry_page is "home"\n'
        'page is "home" at "/":\n'
        '  title "Home"\n'
        '  ai_call "summarise"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "summarise":\n'
        '  model is "default"\n'
    )
    (tmp_path / "app.ai").write_text(program_text, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=True)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))

    monkeypatch.setattr(
        runtime_context,
        "get_last_recall_snapshot",
        lambda ai, session: {
            "timestamp": "now",
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            "diagnostics": [{"source": "short_term", "selected_count": 2, "limit": 10}],
            "rules": [],
        },
    )
    monkeypatch.setattr(
        mem_inspection,
        "describe_memory_state",
        lambda engine, ai_call, session_id=None, limit=50, user_id=None: {"ai": ai_call.name, "session_id": session_id},
    )

    resp = client.get("/api/studio/ai-call", params={"ai": "summarise", "session": "abc"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ai_id"] == "summarise"
    assert payload["session_id"] == "abc"
    assert len(payload.get("messages") or []) == 2
    assert payload["memory"]["ai"] == "summarise"


def test_rag_pipeline_endpoints(tmp_path: Path):
    program_text = Path("examples/rag_qa/rag_qa.ai").read_text(encoding="utf-8")
    (tmp_path / "app.ai").write_text(program_text, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=True)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))

    list_resp = client.get("/api/studio/rag/list")
    assert list_resp.status_code == 200
    pipelines = list_resp.json().get("pipelines") or []
    assert "kb_qa" in pipelines

    detail_resp = client.get("/api/studio/rag/pipeline", params={"name": "kb_qa"})
    assert detail_resp.status_code == 200
    manifest = detail_resp.json()
    assert manifest["name"] == "kb_qa"
    assert len(manifest.get("stages") or []) >= 1


def test_reparse_endpoint_success(tmp_path: Path):
    (tmp_path / "app.ai").write_text(PROGRAM_TEXT, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=False)
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))
    resp = client.post("/api/studio/reparse")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert isinstance(payload.get("timestamp"), str)


def test_reparse_endpoint_reports_errors(tmp_path: Path):
    (tmp_path / "app.ai").write_text(PROGRAM_TEXT, encoding="utf-8")
    daemon = StudioDaemon(tmp_path)
    daemon.ensure_program(raise_on_error=False)

    def fake_ensure(raise_on_error: bool = True):
        daemon.last_error_detail = {"file": "app.ai", "line": 1, "message": "bad"}
        return None

    daemon.ensure_program = fake_ensure  # type: ignore
    client = TestClient(create_app(project_root=tmp_path, daemon_state=daemon))
    resp = client.post("/api/studio/reparse")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is False
    assert payload["errors"]


def test_pages_endpoint_lists_pages():
    code = (
        'page is "home" at "/":\n'
        '  title "Home"\n'
        'page is "about" at "/about":\n'
        '  title "About"\n'
    )
    client = TestClient(create_app())
    response = client.post("/api/pages", json={"code": code}, headers={"X-API-Key": "viewer-key"})
    assert response.status_code == 200
    names = [p["name"] for p in response.json()["pages"]]
    assert "home" in names and "about" in names


def test_page_ui_endpoint_returns_sections():
    code = (
        'page is "home" at "/":\n'
        '  title "Home"\n'
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
        'page is "home" at "/":\n'
        '  title "Home"\n'
        'flow is "pipeline":\n'
        '  step is "call":\n'
        '    kind is "ai"\n'
        '    target "summarise_message"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "summarise_message":\n'
        '  model is "default"\n'
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
