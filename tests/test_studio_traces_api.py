import os
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from namel3ss.observability.tracing import default_tracer
from namel3ss.server import create_app


def _client(tmp_path: Path) -> TestClient:
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        return TestClient(create_app())
    finally:
        os.chdir(prev)


def test_studio_traces_and_runs(tmp_path: Path):
    # Seed a trace with a flow + tool span.
    with default_tracer.span("flow.demo", attributes={"flow": "demo"}):
        with default_tracer.span("tool.demo", attributes={"tool": "t1"}):
            time.sleep(0.01)

    (tmp_path / "main.ai").write_text('flow is "noop":\n  step is "s":\n    log info "ok"\n', encoding="utf-8")
    client = _client(tmp_path)

    runs = client.get("/api/studio/runs", headers={"X-API-Key": "dev-key"})
    assert runs.status_code == 200
    run_list = runs.json()["runs"]
    assert run_list
    run_id = run_list[0]["run_id"]

    trace = client.get(f"/api/studio/runs/{run_id}/trace", headers={"X-API-Key": "dev-key"})
    assert trace.status_code == 200
    events = trace.json()["trace"]
    assert any(evt.get("kind") == "flow" for evt in events)
